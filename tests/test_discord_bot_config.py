"""
Testy dla discord_bot/config.py.
Weryfikuje parsowanie zmiennych środowiskowych bota Discord.
"""

import importlib.util
from pathlib import Path

import pytest

# Ładujemy discord_bot/config.py pod unikalną nazwą, żeby uniknąć kolizji
# z innymi plikami config.py w projekcie.
_spec = importlib.util.spec_from_file_location(
    "_discord_bot_config_module",
    Path(__file__).parent.parent / "discord_bot" / "config.py",
)
assert _spec is not None and _spec.loader is not None
_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cfg)


# ---------------------------------------------------------------------------
# _parse_csv_ids
# ---------------------------------------------------------------------------


def test_parse_csv_ids_single():
    """Pojedyncze ID → zbiór z jednym elementem."""
    assert _cfg._parse_csv_ids("123456789", "TEST") == {123456789}


def test_parse_csv_ids_multiple():
    """Kilka ID oddzielonych przecinkami → poprawny zbiór integerów."""
    result = _cfg._parse_csv_ids("111,222,333", "TEST")
    assert result == {111, 222, 333}


def test_parse_csv_ids_with_spaces():
    """Spacje wokół przecinków są ignorowane."""
    result = _cfg._parse_csv_ids("  111 , 222 , 333 ", "TEST")
    assert result == {111, 222, 333}


def test_parse_csv_ids_empty_string():
    """Pusty string → pusty zbiór."""
    assert _cfg._parse_csv_ids("", "TEST") == set()


def test_parse_csv_ids_invalid_raises():
    """Nieliczbowy token → RuntimeError."""
    with pytest.raises(RuntimeError, match="TEST"):
        _cfg._parse_csv_ids("123,abc,456", "TEST")


# ---------------------------------------------------------------------------
# get_discord_token
# ---------------------------------------------------------------------------


def test_discord_token_raises_when_not_set(monkeypatch):
    """Brak DISCORD_TOKEN → RuntimeError."""
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="DISCORD_TOKEN"):
        _cfg.get_discord_token()


def test_discord_token_returns_value(monkeypatch):
    """Ustawiony token → zwracany."""
    monkeypatch.setenv("DISCORD_TOKEN", "Bot.token.xyz")
    assert _cfg.get_discord_token() == "Bot.token.xyz"


# ---------------------------------------------------------------------------
# get_discord_channel_id
# ---------------------------------------------------------------------------


def test_discord_channel_id_none_when_not_set(monkeypatch):
    """Brak DISCORD_CHANNEL_ID → None."""
    monkeypatch.delenv("DISCORD_CHANNEL_ID", raising=False)
    assert _cfg.get_discord_channel_id() is None


def test_discord_channel_id_returns_int(monkeypatch):
    """Ustawiony ID → zwraca int."""
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "987654321")
    assert _cfg.get_discord_channel_id() == 987654321


def test_discord_channel_id_invalid_raises(monkeypatch):
    """Nieliczbowy ID → RuntimeError."""
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "not_a_number")
    with pytest.raises(RuntimeError, match="DISCORD_CHANNEL_ID"):
        _cfg.get_discord_channel_id()


# ---------------------------------------------------------------------------
# get_alert_poll_interval
# ---------------------------------------------------------------------------


def test_alert_poll_interval_default(monkeypatch):
    """Domyślny interwał sprawdzania alertów to 30 sekund."""
    monkeypatch.delenv("ALERT_POLL_INTERVAL_SECONDS", raising=False)
    assert _cfg.get_alert_poll_interval() == 30


def test_alert_poll_interval_custom(monkeypatch):
    """Niestandardowy interwał pobierany z ENV."""
    monkeypatch.setenv("ALERT_POLL_INTERVAL_SECONDS", "60")
    assert _cfg.get_alert_poll_interval() == 60


def test_alert_poll_interval_invalid_raises(monkeypatch):
    """Nieliczbowa wartość → RuntimeError."""
    monkeypatch.setenv("ALERT_POLL_INTERVAL_SECONDS", "abc")
    with pytest.raises(RuntimeError, match="ALERT_POLL_INTERVAL_SECONDS"):
        _cfg.get_alert_poll_interval()


# ---------------------------------------------------------------------------
# get_discord_admin_user_ids
# ---------------------------------------------------------------------------


def test_admin_user_ids_empty_when_not_set(monkeypatch):
    """Brak konfiguracji → pusty zbiór adminów."""
    monkeypatch.delenv("DISCORD_ADMIN_USER_IDS", raising=False)
    assert _cfg.get_discord_admin_user_ids() == set()


def test_admin_user_ids_returns_set_of_ints(monkeypatch):
    """Lista adminów jako CSV → zbiór integerów."""
    monkeypatch.setenv("DISCORD_ADMIN_USER_IDS", "111,222,333")
    assert _cfg.get_discord_admin_user_ids() == {111, 222, 333}
