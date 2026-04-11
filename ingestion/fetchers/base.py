"""
Abstrakcyjna klasa bazowa dla wszystkich fetcherów rynkowych.

Każdy fetcher implementuje metodę fetch(items) → list[PriceRecord]
i dziedziczy logikę retry / rate-limit handling z tej klasy.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import time
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
        # Monotoniczny timestamp (time.monotonic()) do kiedy obowiązuje rate-limit.
        # Aktualizowany przy każdym odebranym statusie 429 — dzięki temu wszystkie
        # kolejne zapytania z tego fetchera automatycznie czekają, aż limit wygaśnie.
        self._rate_limit_until: float = 0.0

    @abc.abstractmethod
    async def fetch(self, items: list[str]) -> list[PriceRecord]:
        """Pobiera ceny dla podanych market_hash_name. Zwraca listę PriceRecord."""

    async def _get(self, url: str, **kwargs: Any) -> Any:
        """
        GET z retry logiką.
        Obsługuje: 429 (Retry-After), 5xx (backoff), błędy sieci.

        Śledzi czas wygaśnięcia rate-limitu na poziomie instancji, dzięki czemu
        kolejne wywołania _get (np. dla następnych itemów w Steam) automatycznie
        czekają, zamiast natychmiast trafiać w kolejny 429.
        """
        # Jeśli poprzednie zapytanie dostało 429, czekaj aż limit minie.
        # Uwaga: _rate_limit_until jest bezpieczny bez blokady — każdy fetcher
        # przetwarza itemy sekwencyjnie (jedno await na item), więc nigdy nie
        # ma dwóch współbieżnych wywołań _get na tej samej instancji fetchera.
        remaining = self._rate_limit_until - time.monotonic()
        if remaining > 0:
            logger.debug(
                "[%s] Oczekiwanie %.0fs (aktywny rate-limit z poprzedniego zapytania)",
                self.MARKET_NAME,
                remaining,
            )
            await asyncio.sleep(remaining)

        for attempt in range(self.MAX_RETRIES):
            try:
                async with self.session.get(url, **kwargs) as resp:
                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", 60))
                        # Zapamiętaj do kiedy obowiązuje rate-limit — dotyczy WSZYSTKICH
                        # kolejnych zapytań z tego fetchera, nie tylko bieżącego itemu.
                        self._rate_limit_until = time.monotonic() + retry_after
                        logger.warning(
                            "[%s] Rate limited (429), waiting %.0fs (attempt %d/%d)",
                            self.MARKET_NAME,
                            retry_after,
                            attempt + 1,
                            self.MAX_RETRIES,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status >= 500:
                        wait = self.RETRY_BACKOFF**attempt
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
                wait = self.RETRY_BACKOFF**attempt
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
