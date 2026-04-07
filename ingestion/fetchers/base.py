"""
Abstrakcyjna klasa bazowa dla wszystkich fetcherów rynkowych.

Każdy fetcher implementuje metodę fetch(items) → list[PriceRecord]
i dziedziczy logikę retry / rate-limit handling z tej klasy.
"""
from __future__ import annotations

import abc
import asyncio
import logging
from typing import Any

import aiohttp

from shared.models import PriceRecord

logger = logging.getLogger(__name__)


class BaseFetcher(abc.ABC):
    MARKET_NAME: str = ""
    MAX_RETRIES: int = 3
    RETRY_BACKOFF: float = 2.0  # sekundy, mnożone wykładniczo

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    @abc.abstractmethod
    async def fetch(self, items: list[str]) -> list[PriceRecord]:
        """Pobiera ceny dla podanych market_hash_name. Zwraca listę PriceRecord."""

    async def _get(self, url: str, **kwargs: Any) -> Any:
        """
        GET z retry logiką.
        Obsługuje: 429 (Retry-After), 5xx (backoff), błędy sieci.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                async with self.session.get(url, **kwargs) as resp:
                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", 60))
                        logger.warning(
                            "[%s] Rate limited (429), waiting %.0fs",
                            self.MARKET_NAME,
                            retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status >= 500:
                        wait = self.RETRY_BACKOFF ** attempt
                        logger.warning(
                            "[%s] Server error %d, retry %d/%d in %.0fs",
                            self.MARKET_NAME,
                            resp.status,
                            attempt + 1,
                            self.MAX_RETRIES,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    resp.raise_for_status()
                    return await resp.json(content_type=None)

            except aiohttp.ClientError as exc:
                wait = self.RETRY_BACKOFF ** attempt
                logger.warning(
                    "[%s] Request error (attempt %d/%d): %s — retrying in %.0fs",
                    self.MARKET_NAME,
                    attempt + 1,
                    self.MAX_RETRIES,
                    exc,
                    wait,
                )
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(wait)

        raise RuntimeError(
            f"[{self.MARKET_NAME}] Failed to fetch {url} after {self.MAX_RETRIES} attempts"
        )
