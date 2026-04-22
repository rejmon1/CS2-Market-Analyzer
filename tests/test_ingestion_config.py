"""
Testy dla ingestion/config.py.
Weryfikuje odczyt zmiennych środowiskowych bez bazy danych.
"""

import importlib.util
from pathlib import Path

import pytest

# Ładujemy ingestion/config.py pod unikalną nazwą, żeby uniknąć kolizji
# z plikami config.py innych mikroserwisów.
_spec = importlib.util.spec_from_file_location(
    "_ingestion_config_module",
    Path(__file__).parent.parent / "ingestion" / "config.py",
)
assert _spec is not None and _spec.loader is not None
_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cfg)


# ---------------------------------------------------------------------------
# get_database_url
# ---------------------------------------------------------------------------


def test_database_url_raises_when_not_set(monkeypatch):
    """Brak DATABASE_URL → RuntimeError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        _cfg.get_database_url()


def test_database_url_returns_value(monkeypatch):
    """Ustawiona DATABASE_URL → zwraca ją."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    assert _cfg.get_database_url() == "postgresql://user:pass@localhost/db"


# ---------------------------------------------------------------------------
# get_market_poll_interval
# ---------------------------------------------------------------------------


def test_poll_interval_steam_default(monkeypatch):
    """Domyślny interwał dla Steama to 6000 sekund."""
    monkeypatch.delenv("STEAM_POLL_INTERVAL_SECONDS", raising=False)
    assert _cfg.get_market_poll_interval("steam") == 6000


def test_poll_interval_steam_custom(monkeypatch):
    """Niestandardowy interwał dla Steama — pobierany z ENV."""
    monkeypatch.setenv("STEAM_POLL_INTERVAL_SECONDS", "3600")
    assert _cfg.get_market_poll_interval("steam") == 3600


def test_poll_interval_other_market_default(monkeypatch):
    """Domyślny interwał dla innych rynków to 300 sekund."""
    monkeypatch.delenv("GENERAL_POLL_INTERVAL_SECONDS", raising=False)
    assert _cfg.get_market_poll_interval("skinport") == 300
    assert _cfg.get_market_poll_interval("csfloat") == 300


def test_poll_interval_other_market_custom(monkeypatch):
    """Niestandardowy interwał dla rynków innych niż Steam."""
    monkeypatch.setenv("GENERAL_POLL_INTERVAL_SECONDS", "600")
    assert _cfg.get_market_poll_interval("skinport") == 600


# ---------------------------------------------------------------------------
# get_steamapis_key / get_skinport_credentials / get_csfloat_api_key
# ---------------------------------------------------------------------------


def test_steamapis_key_empty_by_default(monkeypatch):
    """Brak klucza Steam API → pusty string."""
    monkeypatch.delenv("STEAMAPIS_API_KEY", raising=False)
    assert _cfg.get_steamapis_key() == ""


def test_steamapis_key_returns_value(monkeypatch):
    """Ustawiony klucz API Steam → zwracany."""
    monkeypatch.setenv("STEAMAPIS_API_KEY", "abc123")
    assert _cfg.get_steamapis_key() == "abc123"


def test_skinport_credentials_empty_by_default(monkeypatch):
    """Brak kredencjałów Skinport → ("", "")."""
    monkeypatch.delenv("SKINPORT_CLIENT_ID", raising=False)
    monkeypatch.delenv("SKINPORT_CLIENT_SECRET", raising=False)
    assert _cfg.get_skinport_credentials() == ("", "")


def test_skinport_credentials_returns_values(monkeypatch):
    """Ustawione kredencjały Skinport → poprawna krotka."""
    monkeypatch.setenv("SKINPORT_CLIENT_ID", "sp_id")
    monkeypatch.setenv("SKINPORT_CLIENT_SECRET", "sp_secret")
    assert _cfg.get_skinport_credentials() == ("sp_id", "sp_secret")


def test_csfloat_api_key_empty_by_default(monkeypatch):
    """Brak klucza API CSFloat → pusty string."""
    monkeypatch.delenv("CSFLOAT_API_KEY", raising=False)
    assert _cfg.get_csfloat_api_key() == ""


def test_csfloat_api_key_returns_value(monkeypatch):
    """Ustawiony klucz API CSFloat → zwracany."""
    monkeypatch.setenv("CSFLOAT_API_KEY", "cf_xyz")
    assert _cfg.get_csfloat_api_key() == "cf_xyz"
