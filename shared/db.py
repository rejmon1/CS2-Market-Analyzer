"""
Narzędzia do operacji na bazie danych (psycopg2).

Używane przez: ingestion, analysis, discord_bot.
Wszystkie funkcje przyjmują otwarte połączenie psycopg2 jako pierwszy argument,
dzięki czemu zarządzanie transakcjami należy do wywołującego.
"""
from __future__ import annotations

import json
import os
from typing import Any

import psycopg2
import psycopg2.extras

from shared.models import Alert, Item, MarketFee, PriceRecord


def get_connection():
    """Zwraca nowe połączenie psycopg2 na podstawie DATABASE_URL."""
    return psycopg2.connect(os.environ["DATABASE_URL"])


# ---------------------------------------------------------------------------
# items
# ---------------------------------------------------------------------------

def items_count(conn) -> int:
    """Zwraca łączną liczbę wierszy w tabeli items."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM items")
        return cur.fetchone()[0]


def get_active_items(conn) -> list[str]:
    """Zwraca market_hash_name wszystkich aktywnych itemów."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT market_hash_name FROM items WHERE is_active = TRUE ORDER BY market_hash_name"
        )
        return [row[0] for row in cur.fetchall()]


def seed_items(conn, market_hash_names: list[str]) -> int:
    """
    Wstawia listę itemów (ON CONFLICT DO NOTHING).
    Zwraca liczbę faktycznie dodanych wierszy.
    """
    inserted = 0
    with conn.cursor() as cur:
        for name in market_hash_names:
            cur.execute(
                "INSERT INTO items (market_hash_name) VALUES (%s) ON CONFLICT DO NOTHING",
                (name,),
            )
            inserted += cur.rowcount
    conn.commit()
    return inserted


def upsert_item(conn, market_hash_name: str, added_by: str | None = None) -> None:
    """
    Dodaje nowy item lub reaktywuje istniejący (is_active = TRUE).
    Używane przez Discord bota (komenda !add_item).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO items (market_hash_name, added_by)
            VALUES (%s, %s)
            ON CONFLICT (market_hash_name) DO UPDATE
                SET is_active = TRUE,
                    added_by  = EXCLUDED.added_by
            """,
            (market_hash_name, added_by),
        )
    conn.commit()


def deactivate_item(conn, market_hash_name: str) -> bool:
    """
    Deaktywuje śledzenie itemu (soft-delete). Zwraca True jeśli item istniał.
    Używane przez Discord bota (komenda !remove_item).
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE items SET is_active = FALSE WHERE market_hash_name = %s",
            (market_hash_name,),
        )
        updated = cur.rowcount
    conn.commit()
    return updated > 0


# ---------------------------------------------------------------------------
# prices
# ---------------------------------------------------------------------------

def insert_prices(conn, records: list[PriceRecord]) -> int:
    """
    Bulk-insert listy PriceRecord do tabeli prices.
    Wymaga, by item już istniał w tabeli items.
    Zwraca liczbę wstawionych wierszy.
    """
    if not records:
        return 0

    rows = [
        (
            r.market_hash_name,
            r.market,
            r.lowest_price,
            r.quantity,
            json.dumps(r.raw_data),
            r.fetched_at.isoformat(),
        )
        for r in records
    ]

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO prices (item_id, market, lowest_price, quantity, raw_data, fetched_at)
            SELECT i.id,
                   v.market,
                   v.lowest_price::numeric,
                   v.quantity::integer,
                   v.raw_data::jsonb,
                   v.fetched_at::timestamptz
            FROM (VALUES %s) AS v(market_hash_name, market, lowest_price, quantity, raw_data, fetched_at)
            JOIN items i ON i.market_hash_name = v.market_hash_name
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def get_latest_prices(conn, market_hash_name: str) -> list[dict[str, Any]]:
    """
    Zwraca ostatni odczyt ceny dla każdego rynku dla danego itemu.
    Używane przez Discord bota (komenda !price).
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (p.market)
                   p.market,
                   p.lowest_price,
                   p.quantity,
                   p.fetched_at
            FROM prices p
            JOIN items i ON i.id = p.item_id
            WHERE i.market_hash_name = %s
            ORDER BY p.market, p.fetched_at DESC
            """,
            (market_hash_name,),
        )
        return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# alerts
# ---------------------------------------------------------------------------

def insert_alert(conn, item_id: int, alert_type: str, details: dict[str, Any]) -> int:
    """Wstawia nowy alert i zwraca jego id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO alerts (item_id, alert_type, details)
            VALUES (%s, %s, %s::jsonb)
            RETURNING id
            """,
            (item_id, alert_type, json.dumps(details)),
        )
        alert_id = cur.fetchone()[0]
    conn.commit()
    return alert_id


def get_unsent_alerts(conn) -> list[dict[str, Any]]:
    """
    Zwraca niesłane alerty wraz z market_hash_name itemu.
    Używane przez Discord bota.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT a.id, a.alert_type, a.details, a.created_at, i.market_hash_name
            FROM alerts a
            JOIN items i ON i.id = a.item_id
            WHERE a.sent = FALSE
            ORDER BY a.created_at ASC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def mark_alerts_sent(conn, alert_ids: list[int]) -> None:
    """Oznacza podane alerty jako wysłane."""
    if not alert_ids:
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE alerts SET sent = TRUE WHERE id = ANY(%s)",
            (alert_ids,),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# market_fees
# ---------------------------------------------------------------------------

def get_market_fees(conn) -> dict[str, MarketFee]:
    """
    Zwraca prowizje wszystkich rynków jako słownik {market: MarketFee}.
    Wartości pochodzą z tabeli market_fees (domyślne seed z init.sql).
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT market, seller_fee, buyer_fee FROM market_fees")
        return {
            row["market"]: MarketFee(
                market=row["market"],
                seller_fee=float(row["seller_fee"]),
                buyer_fee=float(row["buyer_fee"]),
            )
            for row in cur.fetchall()
        }


def get_all_latest_prices(conn) -> dict[str, list[dict[str, Any]]]:
    """
    Zwraca ostatni odczyt ceny z każdego rynku dla wszystkich aktywnych itemów.
    Wynik: { market_hash_name: [ {market, lowest_price, quantity, fetched_at}, ... ] }
    Używane przez silnik analityczny.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (i.market_hash_name, p.market)
                   i.market_hash_name,
                   p.market,
                   p.lowest_price,
                   p.quantity,
                   p.fetched_at
            FROM prices p
            JOIN items i ON i.id = p.item_id
            WHERE i.is_active = TRUE
            ORDER BY i.market_hash_name, p.market, p.fetched_at DESC
            """
        )
        result: dict[str, list[dict[str, Any]]] = {}
        for row in cur.fetchall():
            name = row["market_hash_name"]
            result.setdefault(name, []).append(
                {
                    "market": row["market"],
                    "lowest_price": float(row["lowest_price"]),
                    "quantity": row["quantity"],
                    "fetched_at": row["fetched_at"],
                }
            )
        return result
