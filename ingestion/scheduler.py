"""
Główna pętla schedulera serwisu ingestion.

Schemat działania:
  1. Czeka na gotowość bazy danych (retry z backoffem).
  2. Jeśli tabela items jest pusta → seeduje z default_items.json.
  3. Co POLL_INTERVAL_SECONDS:
     a. Pobiera listę aktywnych itemów z bazy.
     b. Uruchamia wszystkie fetchers równolegle (asyncio.gather).
     c. Bulk-insertuje wyniki do tabeli prices.
     d. Loguje podsumowanie.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import aiohttp

import config
from fetchers.base import BaseFetcher
from fetchers.csfloat import CSFloatFetcher
from fetchers.skinport import SkinportFetcher
from fetchers.steam import SteamFetcher
from shared.db import (
    get_active_items,
    get_connection,
    insert_prices,
    items_count,
    seed_items,
)
from shared.logger import get_logger
from shared.models import PriceRecord

logger = get_logger("ingestion.scheduler")

DEFAULT_ITEMS_PATH = Path(__file__).parent / "default_items.json"
DB_CONNECT_RETRIES = 10
DB_CONNECT_DELAY = 5  # sekundy między próbami połączenia


async def _wait_for_db():
    """Próbuje połączyć się z bazą do DB_CONNECT_RETRIES razy."""
    for attempt in range(1, DB_CONNECT_RETRIES + 1):
        try:
            conn = get_connection()
            logger.info("Database connection established")
            return conn
        except Exception as exc:
            logger.warning(
                "DB not ready (attempt %d/%d): %s", attempt, DB_CONNECT_RETRIES, exc
            )
            await asyncio.sleep(DB_CONNECT_DELAY)
    raise RuntimeError(
        f"Could not connect to database after {DB_CONNECT_RETRIES} attempts"
    )


def _seed_if_empty(conn) -> None:
    """Seeduje tabelę items z default_items.json jeśli jest pusta."""
    if items_count(conn) > 0:
        return
    default_items: list[str] = json.loads(DEFAULT_ITEMS_PATH.read_text())
    inserted = seed_items(conn, default_items)
    logger.info("Seeded %d default items into items table", inserted)


def _build_fetchers(session: aiohttp.ClientSession) -> list[BaseFetcher]:
    """Buduje listę aktywnych fetcherów na podstawie dostępnych kluczy API."""
    fetchers: list[BaseFetcher] = [SteamFetcher(session)]

    skinport_id, skinport_secret = config.get_skinport_credentials()
    if skinport_id and skinport_secret:
        fetchers.append(SkinportFetcher(session, skinport_id, skinport_secret))
    else:
        logger.warning(
            "SKINPORT_CLIENT_ID / SKINPORT_CLIENT_SECRET not set — Skinport disabled"
        )

    csfloat_key = config.get_csfloat_api_key()
    if csfloat_key:
        fetchers.append(CSFloatFetcher(session, csfloat_key))
    else:
        logger.warning("CSFLOAT_API_KEY not set — CSFloat disabled")

    return fetchers


async def _run_poll_cycle(
    fetchers: list[BaseFetcher], items: list[str]
) -> list[PriceRecord]:
    """Uruchamia wszystkie fetchers równolegle i scala wyniki."""
    results = await asyncio.gather(
        *[f.fetch(items) for f in fetchers],
        return_exceptions=True,
    )
    all_records: list[PriceRecord] = []
    for fetcher, result in zip(fetchers, results):
        if isinstance(result, Exception):
            logger.error("[%s] Fetcher failed: %s", fetcher.MARKET_NAME, result)
        else:
            all_records.extend(result)
    return all_records


async def run(poll_interval: int) -> None:
    """Główna pętla schedulera — uruchamiana przez main.py."""
    conn = await _wait_for_db()
    _seed_if_empty(conn)

    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        fetchers = _build_fetchers(session)
        logger.info(
            "Starting scheduler with %d fetcher(s): %s",
            len(fetchers),
            [f.MARKET_NAME for f in fetchers],
        )

        while True:
            try:
                items = get_active_items(conn)
                if not items:
                    logger.warning("No active items — skipping poll cycle")
                    await asyncio.sleep(poll_interval)
                    continue

                logger.info(
                    "Poll cycle: %d items × %d markets", len(items), len(fetchers)
                )
                t0 = time.monotonic()

                records = await _run_poll_cycle(fetchers, items)
                inserted = insert_prices(conn, records)

                elapsed = time.monotonic() - t0
                logger.info(
                    "Poll cycle done: %d price records inserted in %.1fs — sleeping %ds",
                    inserted,
                    elapsed,
                    poll_interval,
                )

            except Exception as exc:
                logger.error("Poll cycle error: %s", exc, exc_info=True)
                # Spróbuj odtworzyć połączenie z bazą po błędzie
                try:
                    conn.close()
                except Exception:
                    pass
                try:
                    conn = get_connection()
                    logger.info("Database connection re-established")
                except Exception as reconnect_exc:
                    logger.error("Failed to reconnect to database: %s", reconnect_exc)

            await asyncio.sleep(poll_interval)
