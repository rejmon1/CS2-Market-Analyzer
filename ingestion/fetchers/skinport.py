"""
Skinport fetcher.

Endpoint: GET https://api.skinport.com/v1/items?app_id=730&currency=USD

Jedno zapytanie zwraca WSZYSTKIE przedmioty — bardzo efektywne.
Auth: HTTP Basic (CLIENT_ID:CLIENT_SECRET zakodowane Base64).
Odpowiedź skompresowana Brotli (wymaga pakietu `brotli`).
"""
from __future__ import annotations

import base64
import logging

import aiohttp

from fetchers.base import BaseFetcher
from shared.models import PriceRecord

logger = logging.getLogger(__name__)

SKINPORT_ITEMS_URL = "https://api.skinport.com/v1/items"


class SkinportFetcher(BaseFetcher):
    MARKET_NAME = "skinport"

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
    ) -> None:
        super().__init__(session)
        credentials = base64.b64encode(
            f"{client_id}:{client_secret}".encode()
        ).decode()
        self._auth_header = f"Basic {credentials}"

    async def fetch(self, items: list[str]) -> list[PriceRecord]:
        items_set = set(items)

        try:
            data = await self._get(
                SKINPORT_ITEMS_URL,
                params={"app_id": "730", "currency": "USD"},
                headers={
                    "Authorization": self._auth_header,
                    # aiohttp + pakiet brotli obsługuje dekompresję automatycznie
                    "Accept-Encoding": "br, gzip, deflate",
                },
            )
        except Exception as exc:
            logger.error("[skinport] Failed to fetch item list: %s", exc)
            return []

        records: list[PriceRecord] = []
        for entry in data:
            name = entry.get("market_hash_name", "")
            if name not in items_set:
                continue

            min_price = entry.get("min_price")
            if min_price is None:
                continue

            records.append(
                PriceRecord(
                    market_hash_name=name,
                    market=self.MARKET_NAME,
                    lowest_price=float(min_price),
                    quantity=int(entry.get("quantity") or 0),
                    raw_data=entry,
                )
            )

        logger.info("[skinport] Fetched %d/%d items", len(records), len(items))
        return records
