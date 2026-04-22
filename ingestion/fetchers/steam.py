"""
SteamAPIs.com fetcher dla Steam Community Market.

Endpoint: GET https://api.steamapis.com/market/items/730?api_key=<KEY>

Jedno zapytanie zwraca WSZYSTKIE przedmioty CS2 — bardzo efektywne.
Wymaga klucza API z https://steamapis.com (plan darmowy: 500 req/miesiąc).

Budżet darmowego planu:
  500 req / 30 dni ≈ 16.7 req/dzień
  Zalecany margines: ~14 req/dzień → POLL_INTERVAL_SECONDS ≥ 6000 (ok. 100 min)

Struktura odpowiedzi:
  {
    "data": [
      {
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "prices": {
          "safe":   12.50,   ← filtrowana cena medialna (historyczna, nie używana)
          "latest": 12.80,   ← ostatnia sprzedaż
          "avg":    12.10,
          "sold":   { "last_7d": 42, ... }
        }
      },
      ...
    ]
  }

Dla `lowest_price` używamy wyłącznie `prices.latest` (ostatnia transakcja — aktualny kurs rynkowy).
Gdy `latest` jest niedostępne, przedmiot jest pomijany (brak aktywnych ofert na Steam).
`prices.safe` (filtrowana mediana historyczna) jest ignorowana — nie odzwierciedla bieżącego rynku.
Dla `quantity` używamy `prices.sold.last_7d` (liczba sprzedanych w ostatnich 7 dniach).
"""

from __future__ import annotations

import logging

import aiohttp

from fetchers.base import BaseFetcher
from shared.models import PriceRecord

logger = logging.getLogger(__name__)

STEAMAPIS_ITEMS_URL = "https://api.steamapis.com/market/items/730"


class SteamFetcher(BaseFetcher):
    MARKET_NAME = "steam"

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        super().__init__(session)
        self._api_key = api_key

    async def fetch(self, items: list[str]) -> list[PriceRecord]:
        items_set = set(items)

        try:
            data = await self._get(
                STEAMAPIS_ITEMS_URL,
                params={"api_key": self._api_key},
            )
        except Exception as exc:
            logger.error("[steam] Failed to fetch item list: %s", exc)
            return []

        if not isinstance(data, dict) or "data" not in data:
            logger.error(
                "[steam] Unexpected response structure: %s",
                str(data)[:200],
            )
            return []

        logger.debug("[steam] API returned %d total items", len(data["data"]))

        records: list[PriceRecord] = []
        skipped_no_price = 0

        for entry in data["data"]:
            name = entry.get("market_hash_name", "")
            if name not in items_set:
                continue

            prices = entry.get("prices") or {}

            # Używamy wyłącznie 'latest' (ostatnia transakcja) jako aktualnej ceny rynkowej.
            # Gdy 'latest' jest niedostępne — brak aktywnych ofert na Steam, pomijamy przedmiot.
            # 'safe' (filtrowana mediana historyczna) jest ignorowana — nie odzwierciedla rynku.
            price = prices.get("latest")

            if price is None:
                skipped_no_price += 1
                logger.debug("[steam] Brak ofert na Steam (brak 'latest') dla %r — pomijanie", name)
                continue

            entry["_price_source"] = "latest"

            sold = prices.get("sold") or {}
            quantity = int(sold.get("last_7d") or 0)

            records.append(
                PriceRecord(
                    market_hash_name=name,
                    market=self.MARKET_NAME,
                    lowest_price=float(price),
                    quantity=quantity,
                    raw_data=entry,
                )
            )

        if skipped_no_price:
            logger.info(
                "[steam] Pominięto %d pasujących przedmiotów bez aktywnych ofert na Steam "
                "(brak 'latest')",
                skipped_no_price,
            )
        if not records:
            logger.warning(
                "[steam] Fetched 0/%d items — brak dopasowań z API "
                "(sprawdź LOG_LEVEL=DEBUG dla szczegółów)",
                len(items),
            )
        else:
            logger.info("[steam] Fetched %d/%d items", len(records), len(items))
        return records
