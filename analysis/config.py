"""
Konfiguracja serwisu analysis.
Wszystkie wartości pochodzą ze zmiennych środowiskowych (plik .env).
"""

from __future__ import annotations

import os


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def get_analysis_interval() -> int:
    """Interwał między cyklami analizy w sekundach (domyślnie 60 s)."""
    return int(os.environ.get("ANALYSIS_INTERVAL_SECONDS", "60"))


def get_min_spread_pct() -> float:
    """Minimalny realny spread netto (po prowizjach) do wygenerowania alertu (domyślnie 5%)."""
    return float(os.environ.get("ARBITRAGE_MIN_SPREAD_PCT", "5.0"))
