"""
Serwis inventory — zarządzanie ekwipunkami graczy Steam.
Logika:
  1. Sprawdza bazę pod kątem profili z pending_update = TRUE.
  2. Pobiera przedmioty CS2 z Steam Community Inventory JSON.
  3. Zapisuje stan w user_inventories i odznacza pending_update.
  4. Rejestruje przedmioty w globalnej tabeli items (do śledzenia przez ingestion).
"""

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from inventory import config
from shared import db
from shared.logger import get_logger

logger = get_logger("inventory")


async def fetch_steam_inventory(
    session: aiohttp.ClientSession, steam_id64: str
) -> Optional[List[Dict[str, Any]]]:
    """
    Pobiera i parsuje ekwipunek CS2 ze Steama.
    """
    url = config.get_steam_inventory_url(steam_id64)

    # Steam wymaga nagłówków i konkretnych parametrów
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    params = {
        "l": "english",
        "count": 1000,  # Bezpieczna wartość
    }

    logger.info("Pobieranie ekwipunku dla SteamID64: %s (URL: %s)", steam_id64, url)

    try:
        async with session.get(url, headers=headers, params=params, timeout=15) as resp:
            if resp.status == 429:
                logger.warning("Steam Rate Limit (429) dla %s", steam_id64)
                return None
            if resp.status != 200:
                logger.error(
                    "Błąd Steam API %d dla ID %s. Sprawdź czy profil jest publiczny.",
                    resp.status,
                    steam_id64,
                )
                return None

            data = await resp.json()
    except Exception as e:
        logger.error("Błąd połączenia ze Steam dla %s: %s", steam_id64, e)
        return None

    if not data or not data.get("assets"):
        # To zazwyczaj oznacza prywatny ekwipunek lub brak przedmiotów w CS2
        logger.info("Inventory for %s is empty or private", steam_id64)
        return []

    descriptions = {
        (d["classid"], d["instanceid"]): d["market_hash_name"]
        for d in data.get("descriptions", [])
        if d.get("marketable")
    }

    parsed_items = []
    for asset in data["assets"]:
        key = (asset["classid"], asset["instanceid"])
        name = descriptions.get(key)
        if name:
            parsed_items.append(
                {
                    "market_hash_name": name,
                    "asset_id": asset["assetid"],
                    "amount": int(asset.get("amount", 1)),
                }
            )

    return parsed_items


async def process_pending_updates(conn):
    """Przetwarza wszystkie profile oczekujące na aktualizację."""
    pending = db.get_pending_updates(conn)
    if not pending:
        return

    logger.info("Found %d pending inventory updates", len(pending))

    async with aiohttp.ClientSession() as session:
        for p in pending:
            discord_id = p["discord_id"]
            steam_id64 = p["steam_id64"]

            try:
                items = await fetch_steam_inventory(session, steam_id64)

                # Jeśli items to None, oznacza to błąd krytyczny/rate limit -> pomijamy odznaczanie
                if items is None:
                    logger.warning(
                        "Skipping update for %s due to API error (will retry)", discord_id
                    )
                    continue

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
