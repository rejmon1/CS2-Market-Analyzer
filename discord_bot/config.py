"""
Konfiguracja serwisu discord_bot.
Wszystkie wartości pochodzą ze zmiennych środowiskowych (plik .env).
"""

from __future__ import annotations

import os


def _parse_csv_ids(raw: str, env_name: str) -> set[int]:
    ids: set[int] = set()
    for token in raw.split(","):
        value = token.strip()
        if not value:
            continue
        try:
            ids.add(int(value))
        except ValueError as err:
            msg = f"{env_name} must contain comma-separated integers, got token: {value!r}"
            raise RuntimeError(msg) from err
    return ids


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def get_discord_token() -> str:
    token = os.environ.get("DISCORD_TOKEN", "")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set")
    return token


def get_discord_channel_id() -> int | None:
    raw = os.environ.get("DISCORD_CHANNEL_ID", "")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as err:
        msg = f"DISCORD_CHANNEL_ID must be a valid integer, got: {raw!r}"
        raise RuntimeError(msg) from err


def get_alert_poll_interval() -> int:
    """Interwał między sprawdzaniem nowych alertów w sekundach (domyślnie 30 s)."""
    raw = os.environ.get("ALERT_POLL_INTERVAL_SECONDS", "30")
    try:
        return int(raw)
    except ValueError as err:
        msg = f"ALERT_POLL_INTERVAL_SECONDS must be a valid integer, got: {raw!r}"
        raise RuntimeError(msg) from err


def get_discord_admin_user_ids() -> set[int]:
    """Lista adminów bota (Discord user IDs), np. 123,456,789."""
    raw = os.environ.get("DISCORD_ADMIN_USER_IDS", "").strip()
    if not raw:
        return set()
    return _parse_csv_ids(raw, "DISCORD_ADMIN_USER_IDS")
