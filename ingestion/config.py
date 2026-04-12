"""
Konfiguracja serwisu ingestion.
Wszystkie wartości pochodzą ze zmiennych środowiskowych (plik .env).
"""

from __future__ import annotations

import os


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def get_market_poll_interval(market_name: str) -> int:
    """Zwraca interwał między cyklami pobierania (w sekundach) dla konkretnego rynku.
    Steam z limitami ma domyślnie 6000s (100 minut).
    Pozostałe darmowe bulk-API (Skinport, CSFloat) mogą działać domyślnie co 300s (5 minut).
    """
    if market_name == "steam":
        return int(os.environ.get("STEAM_POLL_INTERVAL_SECONDS", "6000"))
    return int(os.environ.get("GENERAL_POLL_INTERVAL_SECONDS", "300"))


def get_steamapis_key() -> str:
    """Zwraca klucz API steamapis.com lub "" jeśli nie skonfigurowany.
    Plan darmowy: 500 req/miesiąc → zalecany POLL_INTERVAL_SECONDS >= 6000.
    """
    return os.environ.get("STEAMAPIS_API_KEY", "")


def get_skinport_credentials() -> tuple[str, str]:
    """Zwraca (client_id, client_secret) lub ("", "") jeśli nie skonfigurowane."""
    return (
        os.environ.get("SKINPORT_CLIENT_ID", ""),
        os.environ.get("SKINPORT_CLIENT_SECRET", ""),
    )


def get_csfloat_api_key() -> str:
    """Zwraca klucz API CSFloat lub "" jeśli nie skonfigurowany."""
    return os.environ.get("CSFLOAT_API_KEY", "")
