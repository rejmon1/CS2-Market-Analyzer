"""
Testy dla czystych funkcji pomocniczych z discord_bot/main.py:
  _fmt_price_row  — formatowanie wiersza ceny per rynek
  _fmt_alert      — formatowanie wiadomości alertu
  _is_admin_user  — sprawdzenie czy ID to admin

Moduł discord_bot/main.py wymaga zainstalowanego discord.py — w conftest.py
skonfigurowano odpowiednie mocki. Importujemy main.py z odpowiednią podmianą
sys.modules["config"] na discord_bot/config.py (nie ingestion/config.py).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Załaduj discord_bot/config.py jako "config" przed importem main.py.
# Cel: discord_bot/main.py robi `import config` — musi dostać SWÓJ config,
# nie ingestion/config.py (który byłby domyślnym z powodu pythonpath).
# ---------------------------------------------------------------------------
_DISCORD_BOT_DIR = str(Path(__file__).parent.parent / "discord_bot")
_db_cfg_spec = importlib.util.spec_from_file_location(
    "config", _DISCORD_BOT_DIR + "/config.py"
)
_discord_bot_config = importlib.util.module_from_spec(_db_cfg_spec)
_db_cfg_spec.loader.exec_module(_discord_bot_config)
sys.modules["config"] = _discord_bot_config

# Dodaj discord_bot/ do sys.path — `import main` znajdzie discord_bot/main.py
if _DISCORD_BOT_DIR not in sys.path:
    sys.path.insert(0, _DISCORD_BOT_DIR)

import main as _bot_main  # noqa: E402 — must come after sys.path manipulation

# Przywróć ingestion/config jako "config", żeby nie zakłócać test_scheduler.py
_INGESTION_DIR = str(Path(__file__).parent.parent / "ingestion")
_ing_cfg_spec = importlib.util.spec_from_file_location(
    "config", _INGESTION_DIR + "/config.py"
)
_ingestion_config_restored = importlib.util.module_from_spec(_ing_cfg_spec)
_ing_cfg_spec.loader.exec_module(_ingestion_config_restored)
sys.modules["config"] = _ingestion_config_restored


# ---------------------------------------------------------------------------
# _fmt_alert
# ---------------------------------------------------------------------------


def test_fmt_alert_arbitrage():
    """Alert arbitrażowy powinien zawierać nazwy rynków, ceny i spread."""
    alert = {
        "alert_type": "arbitrage",
        "market_hash_name": "AK-47 | Redline (FT)",
        "details": {
            "market_buy": "steam",
            "market_sell": "skinport",
            "price_buy_raw": 10.5,
            "price_sell_raw": 13.0,
            "spread_pct": 17.6,
            "quantity_sell": 25,
        },
    }
    result = _bot_main._fmt_alert(alert)
    assert "AK-47 | Redline (FT)" in result
    assert "steam" in result
    assert "skinport" in result
    assert "17.6%" in result
    assert "10.5" in result
    assert "13.0" in result


def test_fmt_alert_inventory_value_increase():
    """Alert wzrostu wartości ekwipunku — emoji 📈 i poprawne wartości."""
    alert = {
        "alert_type": "inventory_value",
        "market_hash_name": None,
        "details": {
            "discord_id": "12345",
            "values": {"steam": 200.0, "skinport": 210.0},
            "old_total": 380.0,
            "new_total": 410.0,
            "diff_pct": 7.89,
        },
    }
    result = _bot_main._fmt_alert(alert)
    assert "📈" in result
    assert "+7.89%" in result
    assert "410.00" in result


def test_fmt_alert_inventory_value_decrease():
    """Alert spadku wartości ekwipunku — emoji 📉."""
    alert = {
        "alert_type": "inventory_value",
        "market_hash_name": None,
        "details": {
            "discord_id": "99",
            "values": {"steam": 100.0},
            "old_total": 120.0,
            "new_total": 100.0,
            "diff_pct": -16.67,
        },
    }
    result = _bot_main._fmt_alert(alert)
    assert "📉" in result
    assert "-16.67%" in result


def test_fmt_alert_unknown_type():
    """Nieznany typ alertu → fallback z surowym opisem."""
    alert = {
        "alert_type": "pump_dump",
        "market_hash_name": "Some Item",
        "details": {"reason": "volume spike"},
    }
    result = _bot_main._fmt_alert(alert)
    assert "pump_dump" in result


# ---------------------------------------------------------------------------
# _fmt_price_row
# ---------------------------------------------------------------------------


def test_fmt_price_row_steam():
    """Wiersz ceny dla rynku Steam powinien zawierać cenę min i statystyki."""
    now = datetime.now(timezone.utc)
    row = {
        "market": "steam",
        "lowest_price": 12.5,
        "quantity": 100,
        "fetched_at": now,
        "raw_data": {
            "prices": {
                "min": 12.5,
                "median": 13.0,
                "sold": {"last_7d": 42},
            }
        },
    }
    result = _bot_main._fmt_price_row(row)
    assert "steam" in result
    assert "12.50" in result
    assert "42" in result


def test_fmt_price_row_skinport():
    """Wiersz ceny dla Skinport powinien zawierać min_price i quantity."""
    now = datetime.now(timezone.utc)
    row = {
        "market": "skinport",
        "lowest_price": 9.99,
        "quantity": 15,
        "fetched_at": now,
        "raw_data": {"min_price": 9.99, "median_price": 10.5},
    }
    result = _bot_main._fmt_price_row(row)
    assert "skinport" in result
    assert "9.99" in result
    assert "15" in result


def test_fmt_price_row_csfloat():
    """Wiersz ceny dla CSFloat z ceną w centach (konwersja / 100)."""
    now = datetime.now(timezone.utc)
    row = {
        "market": "csfloat",
        "lowest_price": 11.0,
        "quantity": 5,
        "fetched_at": now,
        "raw_data": {"min_price": 1100},
    }
    result = _bot_main._fmt_price_row(row)
    assert "csfloat" in result
    assert "11.00" in result


# ---------------------------------------------------------------------------
# _is_admin_user
# ---------------------------------------------------------------------------


def test_is_admin_user_when_in_set(monkeypatch):
    """ID będące w zestawie adminów → True."""
    monkeypatch.setattr(_bot_main, "DISCORD_ADMIN_USER_IDS", {111, 222, 333})
    assert _bot_main._is_admin_user(222) is True


def test_is_admin_user_when_not_in_set(monkeypatch):
    """ID spoza zestawu adminów → False."""
    monkeypatch.setattr(_bot_main, "DISCORD_ADMIN_USER_IDS", {111, 222})
    assert _bot_main._is_admin_user(999) is False


def test_is_admin_user_empty_set(monkeypatch):
    """Pusty zestaw adminów → zawsze False."""
    monkeypatch.setattr(_bot_main, "DISCORD_ADMIN_USER_IDS", set())
    assert _bot_main._is_admin_user(111) is False
