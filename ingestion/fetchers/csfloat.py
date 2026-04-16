"""
CSFloat fetcher.

Endpoint: GET https://csfloat.com/api/v1/listings/price-list

Zwraca zbiorczą listę cen wszystkich przedmiotów. Cena w centach (integer) → USD.
Auth: nagłówek "Authorization: <API_KEY>".
Zaleta: Jedno zapytanie dla wszystkich itemów, brak ryzyka rate-limit przy wielu itemach.
"""

from __future__ import annotations

import logging

import aiohttp

from fetchers.base import BaseFetcher
from shared.models import PriceRecord

logger = logging.getLogger(__name__)

CSFLOAT_PRICE_LIST_URL = "https://csfloat.com/api/v1/listings/price-list"


class CSFloatFetcher(BaseFetcher):
    MARKET_NAME = "csfloat"

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        super().__init__(session)
        self._api_key = api_key

    async def fetch(self, items: list[str]) -> list[PriceRecord]:
        items_set = set(items)
        records: list[PriceRecord] = []

        try:
            # Pobieramy całą listę cen w jednym zapytaniu
            data = await self._get(
                CSFLOAT_PRICE_LIST_URL,
                headers={"Authorization": self._api_key},
            )

            # Obsługa: [{"market_hash_name": "...", "min_price": 71, "quantity": 198}]
            if not isinstance(data, list):
                logger.error("[csfloat] Unexpected response type: %s", type(data).__name__)
                return []

            logger.debug("[csfloat] API returned %d items", len(data))

            for stats in data:
                name = stats.get("market_hash_name")
                if not name or name not in items_set:
                    continue

                # Cena w centach -> USD
                price_cents = stats.get("min_price")
                if price_cents is None:
                    continue

                quantity = int(stats.get("quantity") or 0)
                stats["_price_source"] = "min_price"

                records.append(
                    PriceRecord(
                        market_hash_name=name,
                        market=self.MARKET_NAME,
                        lowest_price=round(price_cents / 100, 5),
                        quantity=quantity,
                        raw_data=stats,
                    )
                )

        except Exception as exc:
            logger.error("[csfloat] Failed to fetch price list: %s", exc)

        logger.info("[csfloat] Fetched %d/%d items", len(records), len(items))
        return records
