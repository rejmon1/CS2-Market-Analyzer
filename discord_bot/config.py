"""
Konfiguracja serwisu discord_bot.
Wszystkie wartości pochodzą ze zmiennych środowiskowych (plik .env).
"""
from __future__ import annotations

import os


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
    except ValueError:
        raise RuntimeError(f"DISCORD_CHANNEL_ID must be a valid integer, got: {raw!r}")


def get_alert_poll_interval() -> int:
    """Interwał między sprawdzaniem nowych alertów w sekundach (domyślnie 30 s)."""
    raw = os.environ.get("ALERT_POLL_INTERVAL_SECONDS", "30")
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"ALERT_POLL_INTERVAL_SECONDS must be a valid integer, got: {raw!r}")
