"""
Testy dla ingestion/scheduler.py:
  _seed_if_empty   — warunkowe seedowanie tabeli items z default_items.json
  _build_fetchers  — budowanie listy fetcherów na podstawie kluczy API
  _run_poll_cycle  — równoległe uruchamianie fetcherów i scalanie wyników

UWAGA: Przed importem scheduler.py wymuszamy załadowanie prawdziwego
       ingestion/config.py jako sys.modules["config"] — test_analysis_engine.py
       mógł wcześniej podmienić ten moduł na MagicMock.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Wymuszamy poprawny config (ingestion/config.py) PRZED importem schedulera.
# ---------------------------------------------------------------------------
_INGESTION_DIR = str(Path(__file__).parent.parent / "ingestion")
_spec = importlib.util.spec_from_file_location(
    "config", _INGESTION_DIR + "/config.py"
)
assert _spec is not None and _spec.loader is not None
_real_ingestion_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_real_ingestion_config)
sys.modules["config"] = _real_ingestion_config

from scheduler import _build_fetchers, _run_poll_cycle, _seed_if_empty  # noqa: E402

from fetchers.csfloat import CSFloatFetcher  # noqa: E402
from fetchers.skinport import SkinportFetcher  # noqa: E402
from fetchers.steam import SteamFetcher  # noqa: E402
from shared.models import PriceRecord  # noqa: E402


# ---------------------------------------------------------------------------
# _seed_if_empty
# ---------------------------------------------------------------------------


def test_seed_if_empty_skips_when_items_exist():
    """Gdy tabela items nie jest pusta, seedowanie jest pomijane."""
    conn = MagicMock()
    with patch("scheduler.items_count", return_value=5) as mock_count, \
         patch("scheduler.seed_items") as mock_seed:
        _seed_if_empty(conn)

    mock_count.assert_called_once_with(conn)
    mock_seed.assert_not_called()


def test_seed_if_empty_seeds_when_empty():
    """Gdy tabela jest pusta, seeduje z default_items.json."""
    conn = MagicMock()
    with patch("scheduler.items_count", return_value=0), \
         patch("scheduler.seed_items") as mock_seed:
        _seed_if_empty(conn)

    mock_seed.assert_called_once()
    call_args = mock_seed.call_args[0]
    # Drugi argument (lista nazw) powinien być niepustą listą stringów
    assert isinstance(call_args[1], list)
    assert len(call_args[1]) > 0
    assert all(isinstance(name, str) for name in call_args[1])


# ---------------------------------------------------------------------------
# _build_fetchers
# ---------------------------------------------------------------------------


def test_build_fetchers_no_keys_returns_empty(monkeypatch):
    """Brak kluczy API → pusta lista fetcherów."""
    monkeypatch.delenv("STEAMAPIS_API_KEY", raising=False)
    monkeypatch.delenv("SKINPORT_CLIENT_ID", raising=False)
    monkeypatch.delenv("SKINPORT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("CSFLOAT_API_KEY", raising=False)
    session = MagicMock()
    fetchers = _build_fetchers(session)
    assert fetchers == []


def test_build_fetchers_only_steam_key(monkeypatch):
    """Tylko klucz Steama → jeden SteamFetcher."""
    monkeypatch.setenv("STEAMAPIS_API_KEY", "steam_test_key")
    monkeypatch.delenv("SKINPORT_CLIENT_ID", raising=False)
    monkeypatch.delenv("SKINPORT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("CSFLOAT_API_KEY", raising=False)
    session = MagicMock()
    fetchers = _build_fetchers(session)
    assert len(fetchers) == 1
    assert isinstance(fetchers[0], SteamFetcher)


def test_build_fetchers_all_keys(monkeypatch):
    """Wszystkie klucze API → lista trzech różnych fetcherów."""
    monkeypatch.setenv("STEAMAPIS_API_KEY", "steam_key")
    monkeypatch.setenv("SKINPORT_CLIENT_ID", "sp_id")
    monkeypatch.setenv("SKINPORT_CLIENT_SECRET", "sp_secret")
    monkeypatch.setenv("CSFLOAT_API_KEY", "cf_key")
    session = MagicMock()
    fetchers = _build_fetchers(session)
    assert len(fetchers) == 3
    types = {type(f) for f in fetchers}
    assert SteamFetcher in types
    assert SkinportFetcher in types
    assert CSFloatFetcher in types


def test_build_fetchers_skinport_without_secret_skipped(monkeypatch):
    """Tylko client_id bez client_secret → Skinport pomijany."""
    monkeypatch.setenv("SKINPORT_CLIENT_ID", "only_id")
    monkeypatch.delenv("SKINPORT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("STEAMAPIS_API_KEY", raising=False)
    monkeypatch.delenv("CSFLOAT_API_KEY", raising=False)
    session = MagicMock()
    fetchers = _build_fetchers(session)
    skinport = [f for f in fetchers if isinstance(f, SkinportFetcher)]
    assert skinport == []


# ---------------------------------------------------------------------------
# _run_poll_cycle
# ---------------------------------------------------------------------------


async def test_run_poll_cycle_merges_results():
    """Wyniki z kilku fetcherów są scalane w jedną listę."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    record_a = PriceRecord("Item A", "steam", 10.0, 100, {}, now)
    record_b = PriceRecord("Item B", "skinport", 9.5, 50, {}, now)

    fetcher_a = MagicMock()
    fetcher_a.MARKET_NAME = "steam"
    fetcher_a.fetch = AsyncMock(return_value=[record_a])

    fetcher_b = MagicMock()
    fetcher_b.MARKET_NAME = "skinport"
    fetcher_b.fetch = AsyncMock(return_value=[record_b])

    items = ["Item A", "Item B"]
    records = await _run_poll_cycle([fetcher_a, fetcher_b], items)

    assert len(records) == 2
    names = {r.market_hash_name for r in records}
    assert names == {"Item A", "Item B"}


async def test_run_poll_cycle_handles_fetcher_exception():
    """Wyjątek w fetcherze jest logowany, a wyniki z innych są zwracane."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    record_ok = PriceRecord("Good Item", "csfloat", 5.0, 10, {}, now)

    failing_fetcher = MagicMock()
    failing_fetcher.MARKET_NAME = "steam"
    failing_fetcher.fetch = AsyncMock(side_effect=RuntimeError("API down"))

    ok_fetcher = MagicMock()
    ok_fetcher.MARKET_NAME = "csfloat"
    ok_fetcher.fetch = AsyncMock(return_value=[record_ok])

    records = await _run_poll_cycle([failing_fetcher, ok_fetcher], ["Good Item"])

    assert len(records) == 1
    assert records[0].market_hash_name == "Good Item"


async def test_run_poll_cycle_empty_fetchers():
    """Pusta lista fetcherów → pusta lista wyników."""
    records = await _run_poll_cycle([], ["Item X"])
    assert records == []
