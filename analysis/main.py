"""
Silnik analityczny CS2-Market-Analyzer.

Cykl pracy (co ANALYSIS_INTERVAL_SECONDS):
  1. Pobierz prowizje rynków z tabeli market_fees.
  2. Pobierz najnowsze ceny wszystkich aktywnych itemów z tabeli prices.
  3. Dla każdego itemu przetestuj wszystkie pary (rynek_kupna, rynek_sprzedaży).
  4. Oblicz realny spread netto uwzględniając prowizje:
       koszt       = cena_kupna  × (1 + buyer_fee_rynku_kupna)
       przychód    = cena_sprzedaży × (1 − seller_fee_rynku_sprzedaży)
       spread_netto = (przychód − koszt) / koszt × 100
  5. Jeśli spread_netto >= ARBITRAGE_MIN_SPREAD_PCT → wstaw alert do bazy.
"""

from __future__ import annotations

import logging
import time
from itertools import permutations
from typing import Any

import config
import psycopg2

from shared import db
from shared.logger import get_logger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Silnik arbitrażowy
# ---------------------------------------------------------------------------


def _find_arbitrage_opportunities(
    prices_by_item: dict[str, list[dict[str, Any]]],
    fees: dict[str, Any],
    min_spread_pct: float,
) -> list[dict[str, Any]]:
    """
    Dla każdego itemu i każdej pary (rynek_kupna, rynek_sprzedaży) oblicza
    realny spread netto. Zwraca listę słowników gotowych do wstawienia jako
    pole `details` alertu arbitrażowego.
    """
    opportunities = []
    min_qty = config.get_min_quantity()

    for market_hash_name, price_list in prices_by_item.items():
        # Zbuduj mapę {market: (price, quantity, source)} dla tego itemu
        market_data: dict[str, tuple[float, int, str]] = {
            p["market"]: (
                p["lowest_price"],
                p.get("quantity", 0),
                (p.get("raw_data") or {}).get("_price_source", "unknown"),
            )
            for p in price_list
        }

        # Testuj wszystkie uporządkowane pary (kup na A, sprzedaj na B)
        for buy_market, sell_market in permutations(market_data.keys(), 2):
            fee_buy = fees.get(buy_market)
            fee_sell = fees.get(sell_market)
            if fee_buy is None or fee_sell is None:
                continue

            price_buy, qty_buy, source_buy = market_data[buy_market]
            price_sell, qty_sell, source_sell = market_data[sell_market]

            # Ignoruj okazje z niskim wolumenem na rynku sprzedaży
            if qty_sell < min_qty:
                continue

            cost = price_buy * (1 + fee_buy.buyer_fee)
            revenue = price_sell * (1 - fee_sell.seller_fee)

            if cost <= 0:
                continue

            spread_pct = (revenue - cost) / cost * 100

            if spread_pct >= min_spread_pct:
                opportunities.append(
                    {
                        "market_hash_name": market_hash_name,
                        "details": {
                            "market_buy": buy_market,
                            "price_buy_raw": round(price_buy, 5),
                            "source_buy": source_buy,
                            "buyer_fee": fee_buy.buyer_fee,
                            "cost": round(cost, 5),
                            "market_sell": sell_market,
                            "price_sell_raw": round(price_sell, 5),
                            "source_sell": source_sell,
                            "seller_fee": fee_sell.seller_fee,
                            "revenue": round(revenue, 5),
                            "spread_pct": round(spread_pct, 2),
                            "quantity_sell": qty_sell,
                        },
                    }
                )

    return opportunities


def _already_alerted_recently(conn, item_id: int, market_buy: str, market_sell: str) -> bool:
    """
    Sprawdza, czy w ciągu ostatnich 24 godzin wygenerowano już alert arbitrażowy
    dla tej samej pary (item, rynek_kupna, rynek_sprzedaży).
    Zapobiega zalewaniu kanału Discord duplikatami.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM alerts
            WHERE item_id    = %s
              AND alert_type = 'arbitrage'
              AND details->>'market_buy'  = %s
              AND details->>'market_sell' = %s
              AND created_at >= NOW() - INTERVAL '24 hours'
            LIMIT 1
            """,
            (item_id, market_buy, market_sell),
        )
        return cur.fetchone() is not None


def check_inventory_trends(conn) -> int:
    """
    Dla każdego użytkownika oblicza aktualną wartość ekwipunku na każdym rynku
    i porównuje sumaryczną wartość z tą sprzed 24h.
    Jeśli zmiana > 5%, generuje alert ze szczegółami per rynek.
    """
    profiles = db.get_all_user_profiles(conn)
    if not profiles:
        return 0

    alerts_created = 0
    for profile in profiles:
        discord_id = profile["discord_id"]
        inventory = db.get_user_inventory(conn, discord_id)
        if not inventory:
            continue

        # Mapa wartości: {market: total_value}
        current_values: dict[str, float] = {}
        historical_values: dict[str, float] = {}

        for item in inventory:
            name = item["market_hash_name"]
            amount = item["amount"]

            # Ceny aktualne ze wszystkich rynków
            latest = db.get_latest_prices(conn, name)
            for p in latest:
                m = p["market"]
                current_values[m] = current_values.get(m, 0.0) + (float(p["lowest_price"]) * amount)

            # Ceny historyczne (sprzed 24h)
            hist = db.get_historical_prices(conn, name, "24 hours")
            for p in hist:
                m = p["market"]
                historical_values[m] = historical_values.get(m, 0.0) + (
                    float(p["lowest_price"]) * amount
                )

        if not current_values:
            continue

        # Do wyliczenia trendu używamy sumy wartości ze wszystkich rynków
        curr_total = sum(current_values.values())
        hist_total = sum(historical_values.values()) if historical_values else curr_total

        if hist_total <= 0:
            continue

        diff_pct = (curr_total - hist_total) / hist_total * 100

        if abs(diff_pct) >= 5.0:
            # Sprawdź czy nie było alertu w ciągu ostatnich 24h
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM alerts "
                    "WHERE alert_type = 'inventory_value' "
                    "AND details->>'discord_id' = %s "
                    "AND created_at >= NOW() - INTERVAL '24 hours'",
                    (discord_id,),
                )
                if cur.fetchone():
                    continue

            db.insert_alert(
                conn,
                item_id=None,
                alert_type="inventory_value",
                details={
                    "discord_id": discord_id,
                    "values": {m: round(v, 2) for m, v in current_values.items()},
                    "old_total": round(hist_total, 2),
                    "new_total": round(curr_total, 2),
                    "diff_pct": round(diff_pct, 2),
                },
            )
            alerts_created += 1
            logger.info("Trend alert dla %s: %.2f%%", discord_id, diff_pct)

    return alerts_created


def run_once(conn) -> int:
    """
    Wykonuje jeden cykl analizy. Zwraca liczbę wygenerowanych alertów.
    """
    min_spread = config.get_min_spread_pct()
    total_alerts = 0

    fees = db.get_market_fees(conn)
    prices_by_item = db.get_all_latest_prices(conn)

    if fees and prices_by_item:
        opportunities = _find_arbitrage_opportunities(prices_by_item, fees, min_spread)

        with conn.cursor() as cur:
            cur.execute("SELECT id, market_hash_name FROM items WHERE is_active = TRUE")
            item_id_map: dict[str, int] = {row[1]: row[0] for row in cur.fetchall()}

        for opp in opportunities:
            name = opp["market_hash_name"]
            details = opp["details"]
            item_id = item_id_map.get(name)
            if item_id and not _already_alerted_recently(
                conn, item_id, details["market_buy"], details["market_sell"]
            ):
                db.insert_alert(conn, item_id, "arbitrage", details)
                total_alerts += 1

    total_alerts += check_inventory_trends(conn)
    return total_alerts


def main() -> None:
    logger = get_logger(__name__)
    logger.info("Analysis service started")

    interval = config.get_analysis_interval()
    min_spread = config.get_min_spread_pct()
    logger.info(
        "Konfiguracja: interwał=%ds, minimalny_spread=%.1f%%",
        interval,
        min_spread,
    )

    while True:
        try:
            conn = db.get_connection()
            try:
                created = run_once(conn)
                logger.info("Cykl zakończony — wygenerowano %d alertów", created)
            finally:
                conn.close()
        except psycopg2.OperationalError as exc:
            logger.error("Błąd połączenia z bazą danych: %s", exc)
        except Exception as exc:
            logger.exception("Nieoczekiwany błąd w cyklu analizy: %s", exc)

        logger.debug("Czekam %d s do następnego cyklu…", interval)
        time.sleep(interval)


if __name__ == "__main__":
    main()
