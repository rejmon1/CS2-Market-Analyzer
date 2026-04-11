"""
Skinport fetcher.

Endpoint: GET https://api.skinport.com/v1/items?app_id=730&currency=USD

Jedno zapytanie zwraca WSZYSTKIE przedmioty — bardzo efektywne.
Auth: HTTP Basic (CLIENT_ID:CLIENT_SECRET zakodowane Base64).
Odpowiedź skompresowana Brotli (wymaga pakietu `brotli`).

Pole cenowe: najpierw sprawdzamy `min_price` (ogólna najniższa cena),
a jeśli jest None — fallback do `min_tradable_price` (najniższa cena
wyłącznie itemów gotowych do wymiany). Skinport może zwracać null
dla jednego z tych pól w zależności od stanu listingów.
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
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
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

        if not isinstance(data, list):
            logger.error(
                "[skinport] Unexpected response type: %s (expected list)", type(data).__name__
            )
            return []

        logger.debug("[skinport] API returned %d total items", len(data))

        records: list[PriceRecord] = []
        skipped_no_price = 0

        for entry in data:
            name = entry.get("market_hash_name", "")
            if name not in items_set:
                continue

            # Preferujemy min_price; fallback do min_tradable_price jeśli None.
            # Skinport może zwracać null dla min_price gdy item nie ma aktywnych
            # listingów ogółem, ale min_tradable_price jest dostępny dla itemów
            # gotowych do wymiany.
            min_price = entry.get("min_price")
            if min_price is None:
                min_price = entry.get("min_tradable_price")
            if min_price is None:
                skipped_no_price += 1
                logger.debug("[skinport] No price for %r — skipping", name)
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

        if skipped_no_price:
            logger.debug(
                "[skinport] Skipped %d matched items with no current price", skipped_no_price
            )
        if not records:
            logger.warning(
                "[skinport] Fetched 0/%d items — brak dopasowań z API "
                "(sprawdź LOG_LEVEL=DEBUG dla szczegółów)",
                len(items),
            )
        else:
            logger.info("[skinport] Fetched %d/%d items", len(records), len(items))
        return records
