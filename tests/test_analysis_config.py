"""
Testy dla analysis/config.py.
Weryfikuje odczyt zmiennych środowiskowych bez bazy danych.
"""

import importlib.util
from pathlib import Path

import pytest

# Ładujemy analysis/config.py pod unikalną nazwą, żeby uniknąć kolizji
# z innymi plikami config.py w projekcie.
_spec = importlib.util.spec_from_file_location(
    "_analysis_config_module",
    Path(__file__).parent.parent / "analysis" / "config.py",
)
_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cfg)


def test_database_url_raises_when_not_set(monkeypatch):
    """Brak DATABASE_URL → RuntimeError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        _cfg.get_database_url()


def test_database_url_returns_value(monkeypatch):
    """Ustawiona DATABASE_URL → zwraca ją."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/cs2")
    assert _cfg.get_database_url() == "postgresql://user:pass@db:5432/cs2"


def test_analysis_interval_default(monkeypatch):
    """Domyślny interwał analizy to 60 sekund."""
    monkeypatch.delenv("ANALYSIS_INTERVAL_SECONDS", raising=False)
    assert _cfg.get_analysis_interval() == 60


def test_analysis_interval_custom(monkeypatch):
    """Niestandardowy interwał — pobierany z ENV."""
    monkeypatch.setenv("ANALYSIS_INTERVAL_SECONDS", "120")
    assert _cfg.get_analysis_interval() == 120


def test_min_spread_pct_default(monkeypatch):
    """Domyślny minimalny spread to 5.0%."""
    monkeypatch.delenv("ARBITRAGE_MIN_SPREAD_PCT", raising=False)
    assert _cfg.get_min_spread_pct() == 5.0


def test_min_spread_pct_custom(monkeypatch):
    """Niestandardowy spread — pobierany z ENV."""
    monkeypatch.setenv("ARBITRAGE_MIN_SPREAD_PCT", "7.5")
    assert _cfg.get_min_spread_pct() == pytest.approx(7.5)


def test_min_quantity_default(monkeypatch):
    """Domyślna minimalna ilość (quantity) to 3."""
    monkeypatch.delenv("ARBITRAGE_MIN_QUANTITY", raising=False)
    assert _cfg.get_min_quantity() == 3


def test_min_quantity_custom(monkeypatch):
    """Niestandardowy próg wolumenu — pobierany z ENV."""
    monkeypatch.setenv("ARBITRAGE_MIN_QUANTITY", "10")
    assert _cfg.get_min_quantity() == 10
