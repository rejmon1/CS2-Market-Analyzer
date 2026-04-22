"""
Testy dla inventory/config.py.
Weryfikuje odczyt zmiennych środowiskowych serwisu ekwipunku.
"""

import importlib.util
from pathlib import Path

# Ładujemy inventory/config.py pod unikalną nazwą, żeby uniknąć kolizji
# z innymi plikami config.py w projekcie.
_spec = importlib.util.spec_from_file_location(
    "_inventory_config_module",
    Path(__file__).parent.parent / "inventory" / "config.py",
)
assert _spec is not None and _spec.loader is not None
_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cfg)


def test_poll_interval_default(monkeypatch):
    """Domyślny interwał odświeżania ekwipunku to 3600 sekund."""
    monkeypatch.delenv("INVENTORY_POLL_INTERVAL", raising=False)
    assert _cfg.get_poll_interval() == 3600


def test_poll_interval_custom(monkeypatch):
    """Niestandardowy interwał pobierany z ENV."""
    monkeypatch.setenv("INVENTORY_POLL_INTERVAL", "1800")
    assert _cfg.get_poll_interval() == 1800


def test_error_retry_default(monkeypatch):
    """Domyślny backoff po błędzie to 300 sekund."""
    monkeypatch.delenv("INVENTORY_ERROR_RETRY_SECONDS", raising=False)
    assert _cfg.get_error_retry_seconds() == 300


def test_error_retry_custom(monkeypatch):
    """Niestandardowy backoff pobierany z ENV."""
    monkeypatch.setenv("INVENTORY_ERROR_RETRY_SECONDS", "120")
    assert _cfg.get_error_retry_seconds() == 120


def test_steam_inventory_url_format():
    """URL ekwipunku Steama zawiera steamID64 i identyfikator gry CS2 (730/2)."""
    url = _cfg.get_steam_inventory_url("76561198000000000")
    assert "76561198000000000" in url
    assert "730/2" in url


def test_steam_inventory_url_different_ids():
    """Różne steamID64 generują różne URL-e."""
    url1 = _cfg.get_steam_inventory_url("76561198000000001")
    url2 = _cfg.get_steam_inventory_url("76561198000000002")
    assert url1 != url2
    assert "76561198000000001" in url1
    assert "76561198000000002" in url2
