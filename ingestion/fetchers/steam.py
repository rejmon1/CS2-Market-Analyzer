"""
Steam Community Market fetcher.

Endpoint: GET https://steamcommunity.com/market/priceoverview/
  ?appid=730&currency=1&market_hash_name=<name>

Brak klucza API. Limit: ~1 zapytanie/sek (publiczne API).
Zwraca cenę najniższego aktywnego listingu w USD.
"""
from __future__ import annotations

import asyncio
import logging
import re

import aiohttp

from fetchers.base import BaseFetcher
from shared.models import PriceRecord

logger = logging.getLogger(__name__)

STEAM_PRICE_URL = "https://steamcommunity.com/market/priceoverview/"
REQUEST_DELAY = 1.2  # sekundy między zapytaniami (Steam: ~1 req/s)


class SteamFetcher(BaseFetcher):
    MARKET_NAME = "steam"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        super().__init__(session)

    async def fetch(self, items: list[str]) -> list[PriceRecord]:
        records: list[PriceRecord] = []

        for item in items:
            try:
                data = await self._get(
                    STEAM_PRICE_URL,
                    params={"appid": "730", "currency": "1", "market_hash_name": item},
                )

                if not data.get("success"):
                    logger.debug("[steam] No data for %r", item)
                    continue

                lowest_price = _parse_steam_price(data.get("lowest_price", ""))
                if lowest_price is None:
                    logger.warning("[steam] Cannot parse price for %r: %s", item, data)
                    continue

                volume_str = data.get("volume", "0").replace(",", "")
                try:
                    quantity = int(volume_str) if volume_str else 0
                except ValueError:
                    quantity = 0

                records.append(
                    PriceRecord(
                        market_hash_name=item,
                        market=self.MARKET_NAME,
                        lowest_price=lowest_price,
                        quantity=quantity,
                        raw_data=data,
                    )
                )

            except Exception as exc:
                logger.error("[steam] Failed to fetch %r: %s", item, exc)

            finally:
                # Zawsze czekaj — nawet po błędzie, by nie przekroczyć limitu
                await asyncio.sleep(REQUEST_DELAY)

        logger.info("[steam] Fetched %d/%d items", len(records), len(items))
        return records


def _parse_steam_price(price_str: str) -> float | None:
    """
    Parsuje cenę Steam w różnych formatach walutowych → float USD.
    Przykłady wejścia: "$12.34", "12,34 €", "1,234.56"
    """
    # Usuń wszystkie znaki niebędące cyframi, kropką ani przecinkiem
    cleaned = re.sub(r"[^\d.,]", "", price_str).strip()
    if not cleaned:
        return None

    if "." in cleaned and "," in cleaned:
        # Sprawdź, który separator pojawia się jako ostatni → to separator dziesiętny
        if cleaned.rfind(".") > cleaned.rfind(","):
            # Format: 1,234.56 — przecinek = tysiące, kropka = decimal
            cleaned = cleaned.replace(",", "")
        else:
            # Format: 1.234,56 — kropka = tysiące, przecinek = decimal
            cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        # Tylko przecinek — sprawdź czy to separator dziesiętny czy tysięcy
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Europejski separator dziesiętny: "12,34" → 12.34
            cleaned = cleaned.replace(",", ".")
        else:
            # Separator tysięcy: "1,234" → 1234
            cleaned = cleaned.replace(",", "")

    try:
        return float(cleaned)
    except ValueError:
        return None
