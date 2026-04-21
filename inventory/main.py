"""
Serwis inventory — zarządzanie ekwipunkami graczy Steam.
Logika:
  1. Sprawdza bazę pod kątem profili z pending_update = TRUE.
  2. Pobiera przedmioty CS2 z Steam Community Inventory JSON.
  3. Zapisuje stan w user_inventories i odznacza pending_update.
  4. Rejestruje przedmioty w globalnej tabeli items (do śledzenia przez ingestion).
"""

import asyncio
import socket
import time
from typing import Any, Dict, List, Optional

import aiohttp

from inventory import config
from shared import db
from shared.logger import get_logger

logger = get_logger("inventory")

_next_retry_by_user: dict[str, float] = {}


async def _fetch_inventory_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    steam_id64: str,
    source: str,
    headers: dict[str, str],
    params: dict[str, Any],
) -> dict[str, Any] | None:
    logger.info(
        "Pobieranie ekwipunku dla SteamID64: %s (source=%s, URL: %s)",
        steam_id64,
        source,
        url,
    )

    try:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 429:
                logger.warning("[%s] Rate Limit (429) dla %s", source, steam_id64)
                return None
            if resp.status != 200:
                response_preview = (await resp.text())[:200].replace("\n", " ")
                logger.error(
                    "[%s] Błąd API %d dla ID %s. Odpowiedź: %s",
                    source,
                    resp.status,
                    steam_id64,
                    response_preview,
                )
                return None

            data = await resp.json(content_type=None)
            return data if isinstance(data, dict) else None
    except Exception as e:
        logger.error(
            "Błąd połączenia [%s] dla %s (%s): %r",
            source,
            steam_id64,
            type(e).__name__,
            e,
        )
        return None


def _parse_inventory_items(
    data: dict[str, Any], steam_id64: str, source: str
) -> list[dict[str, Any]]:
    assets = data.get("assets") or []
    descriptions_raw = data.get("descriptions") or []

    if not assets:
        logger.info("[%s] Inventory for %s is empty or private", source, steam_id64)
        return []

    descriptions = {
        (str(d.get("classid")), str(d.get("instanceid"))): d.get("market_hash_name")
        for d in descriptions_raw
        if d.get("marketable") and d.get("market_hash_name")
    }

    parsed_items: list[dict[str, Any]] = []
    for asset in assets:
        key = (str(asset.get("classid")), str(asset.get("instanceid")))
        name = descriptions.get(key)
        if not isinstance(name, str):
            continue

        try:
            amount = int(asset.get("amount", 1))
        except (TypeError, ValueError):
            amount = 1

        asset_id = str(asset.get("assetid", "")).strip()
        if not asset_id:
            continue

        parsed_items.append(
            {
                "market_hash_name": name,
                "asset_id": asset_id,
                "amount": amount,
            }
        )

    return parsed_items


async def fetch_steam_inventory(
    session: aiohttp.ClientSession, steam_id64: str
) -> Optional[List[Dict[str, Any]]]:
    """
    Pobiera i parsuje ekwipunek CS2 ze Steama.
    """
    steamcommunity_url = config.get_steam_inventory_url(steam_id64)

    # Steam wymaga nagłówków i konkretnych parametrów
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    steamcommunity_params = {
        "l": "english",
        "count": 1000,  # Bezpieczna wartość
    }

    # Publiczne steamcommunity
    steamcommunity_data = await _fetch_inventory_json(
        session,
        steamcommunity_url,
        steam_id64=steam_id64,
        source="steamcommunity",
        headers=headers,
        params=steamcommunity_params,
    )
    if steamcommunity_data is not None:
        return _parse_inventory_items(steamcommunity_data, steam_id64, "steamcommunity")

    return None


async def process_pending_updates(conn):
    """Przetwarza wszystkie profile oczekujące na aktualizację."""
    pending = db.get_pending_updates(conn)
    if not pending:
        return

    logger.info("Found %d pending inventory updates", len(pending))

    retry_backoff = config.get_error_retry_seconds()
    now = time.monotonic()
    connector = aiohttp.TCPConnector(family=socket.AF_INET, limit=10)
    timeout = aiohttp.ClientTimeout(total=25, connect=8, sock_read=15)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for p in pending:
            discord_id = p["discord_id"]
            steam_id64 = p["steam_id64"]

            next_retry = _next_retry_by_user.get(discord_id, 0.0)
            if now < next_retry:
                remaining = int(next_retry - now)
                logger.info(
                    "Skipping update for %s due to backoff (%ds remaining)",
                    discord_id,
                    remaining,
                )
                continue

            try:
                items = await fetch_steam_inventory(session, steam_id64)

                # Jeśli items to None, oznacza to błąd krytyczny/rate limit -> pomijamy odznaczanie
                if items is None:
                    _next_retry_by_user[discord_id] = time.monotonic() + retry_backoff
                    logger.warning(
                        "Skipping update for %s due to API error (will retry in %ds)",
                        discord_id,
                        retry_backoff,
                    )
                    continue

                _next_retry_by_user.pop(discord_id, None)

                # Zapisujemy stan (nawet jeśli lista przedmiotów jest pusta)
                db.update_user_inventory(conn, discord_id, items)

                if items:
                    # Rejestracja w globalnym systemie (dodawanie do items)
                    unique_names = list(set(i["market_hash_name"] for i in items))
                    db.seed_items(conn, unique_names)
                    logger.info("✅ Updated inventory for %s (%d items)", discord_id, len(items))
                else:
                    logger.info("Inventory for %s is empty or private", discord_id)
            except Exception as e:
                logger.error("Error processing update for %s: %s", discord_id, e)


async def main_loop():
    logger.info("Inventory service loop started")
    while True:
        try:
            conn = db.get_connection()
            try:
                await process_pending_updates(conn)
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error in inventory loop: %s", e)

        await asyncio.sleep(10)  # Sprawdzaj co 10 sekund


if __name__ == "__main__":
    asyncio.run(main_loop())
