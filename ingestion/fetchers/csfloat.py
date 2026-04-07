"""
CSFloat fetcher.

Endpoint: GET https://csfloat.com/api/v1/listings
  ?market_hash_name=<name>&limit=1&sort_by=price&order=asc

Zwraca najtańszy aktywny listing. Cena w centach (integer) → dzielimy przez 100.
Auth: nagłówek "Authorization: <API_KEY>".
Limit: ok. 1–2 zapytania/sek; używamy REQUEST_DELAY między itemami.
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from fetchers.base import BaseFetcher
from shared.models import PriceRecord

logger = logging.getLogger(__name__)

CSFLOAT_LISTINGS_URL = "https://csfloat.com/api/v1/listings"
REQUEST_DELAY = 0.6  # sekundy między zapytaniami


class CSFloatFetcher(BaseFetcher):
    MARKET_NAME = "csfloat"

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        super().__init__(session)
        self._api_key = api_key

    async def fetch(self, items: list[str]) -> list[PriceRecord]:
        records: list[PriceRecord] = []

        for item in items:
            try:
                data = await self._get(
                    CSFLOAT_LISTINGS_URL,
                    params={
                        "market_hash_name": item,
                        "limit": "1",
                        "sort_by": "price",
                        "order": "asc",
                    },
                    headers={"Authorization": self._api_key},
                )

                listings = data.get("data", [])
                if not listings:
                    logger.debug("[csfloat] No listings for %r", item)
                    continue

                # Cena w centach → USD
                price_cents = listings[0].get("price")
                if price_cents is None:
                    continue

                records.append(
                    PriceRecord(
                        market_hash_name=item,
                        market=self.MARKET_NAME,
                        lowest_price=round(price_cents / 100, 5),
                        quantity=int(data.get("total_count") or len(listings)),
                        raw_data={
                            "listing": listings[0],
                            "total_count": data.get("total_count", 0),
                        },
                    )
                )

            except Exception as exc:
                logger.error("[csfloat] Failed to fetch %r: %s", item, exc)

            finally:
                await asyncio.sleep(REQUEST_DELAY)

        logger.info("[csfloat] Fetched %d/%d items", len(records), len(items))
        return records
