"""
Testy dla silnika analitycznego (analysis/main.py) — funkcja _find_arbitrage_opportunities.

Ponieważ analysis/main.py korzysta z `import config` (ingestion/config.py lub analysis/config.py
w zależności od pythonpath), a w testach chcemy kontrolować wartość get_min_quantity(),
używamy sys.modules do wstrzyknięcia mocka przed importem modułu analizy.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Konfiguracja ścieżki i mockowanie zależności PRZED importem analysis/main.py
# ---------------------------------------------------------------------------

_ANALYSIS_DIR = Path(__file__).parent.parent / "analysis"

# Wstrzyknij mock konfiguracji (analysis/config.py wymaga get_min_quantity)
_config_mock = MagicMock()
_config_mock.get_min_quantity.return_value = 1  # domyślnie niski próg, by testy były proste
_config_mock.get_min_spread_pct.return_value = 5.0
sys.modules["config"] = _config_mock

# Ładujemy analysis/main.py pod unikalną nazwą, by nie zaśmiecać sys.modules["main"].
_main_spec = importlib.util.spec_from_file_location("_analysis_main", _ANALYSIS_DIR / "main.py")
assert _main_spec is not None and _main_spec.loader is not None
_analysis_main_mod = importlib.util.module_from_spec(_main_spec)
_main_spec.loader.exec_module(_analysis_main_mod)
_find_arbitrage_opportunities = _analysis_main_mod._find_arbitrage_opportunities

# Przywracamy oryginalny stan sys.modules["config"], żeby inne pliki testowe
# (np. test_scheduler.py) mogły załadować swój własny config bez konfliktu.
sys.modules.pop("config", None)

from shared.models import MarketFee  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_min_quantity():
    """Przed każdym testem przywraca domyślną wartość get_min_quantity."""
    _config_mock.get_min_quantity.return_value = 1
    yield


def _make_fees(
    steam_seller: float = 0.15,
    steam_buyer: float = 0.0,
    skinport_seller: float = 0.12,
    skinport_buyer: float = 0.0,
    csfloat_seller: float = 0.02,
    csfloat_buyer: float = 0.0,
) -> dict[str, MarketFee]:
    return {
        "steam": MarketFee("steam", steam_seller, steam_buyer),
        "skinport": MarketFee("skinport", skinport_seller, skinport_buyer),
        "csfloat": MarketFee("csfloat", csfloat_seller, csfloat_buyer),
    }


def _make_price_entry(market: str, price: float, quantity: int = 50) -> dict[str, Any]:
    return {
        "market": market,
        "lowest_price": price,
        "quantity": quantity,
        "raw_data": {"_price_source": "latest"},
    }


# ---------------------------------------------------------------------------
# Testy
# ---------------------------------------------------------------------------


def test_detects_profitable_arbitrage():
    """
    Kupno na steam (niższa cena), sprzedaż na csfloat (wyższa cena, mała prowizja)
    powinno wygenerować okazję arbitrażową.
    """
    # csfloat seller_fee = 2%, steam buyer_fee = 0%
    # Kupno: steam: koszt = 10.0 * (1+0) = 10.0
    # Sprzedaż: csfloat: przychód = 12.0 * (1-0.02) = 11.76
    # spread = (11.76 - 10.0) / 10.0 * 100 = 17.6% > 5% ✓
    prices = {
        "AK-47 | Redline (FT)": [
            _make_price_entry("steam", 10.0, quantity=100),
            _make_price_entry("csfloat", 12.0, quantity=20),
        ]
    }
    fees = _make_fees()

    opps = _find_arbitrage_opportunities(prices, fees, min_spread_pct=5.0)

    assert len(opps) >= 1
    matching = [o for o in opps if o["details"]["market_buy"] == "steam"
                and o["details"]["market_sell"] == "csfloat"]
    assert len(matching) == 1
    opp = matching[0]
    assert opp["market_hash_name"] == "AK-47 | Redline (FT)"
    assert opp["details"]["spread_pct"] == pytest.approx(17.6, abs=0.1)


def test_spread_below_threshold_is_ignored():
    """Spread netto poniżej minimalnego progu → brak alertu."""
    # Kupno steam: 10.0, sprzedaż skinport: 10.5
    # koszt = 10.0; przychód = 10.5 * (1 - 0.12) = 9.24
    # spread = (9.24 - 10.0) / 10.0 * 100 = -7.6% < 5% → brak okazji
    prices = {
        "Boring Item": [
            _make_price_entry("steam", 10.0, quantity=50),
            _make_price_entry("skinport", 10.5, quantity=50),
        ]
    }
    fees = _make_fees()

    opps = _find_arbitrage_opportunities(prices, fees, min_spread_pct=5.0)

    # Żadna kombinacja nie powinna przekroczyć progu 5%
    profitable = [o for o in opps if o["details"]["spread_pct"] >= 5.0]
    assert profitable == []


def test_quantity_below_min_is_ignored():
    """Zbyt niski wolumen na rynku sprzedaży → okazja pomijana."""
    _config_mock.get_min_quantity.return_value = 10

    prices = {
        "Low Volume Item": [
            _make_price_entry("steam", 10.0, quantity=100),
            _make_price_entry("csfloat", 15.0, quantity=2),  # za mało!
        ]
    }
    fees = _make_fees()

    opps = _find_arbitrage_opportunities(prices, fees, min_spread_pct=1.0)

    # csfloat sell: quantity=2 < min_qty=10 → żadna okazja buy_steam/sell_csfloat
    no_csfloat_sell = [
        o for o in opps if o["details"]["market_sell"] == "csfloat"
    ]
    assert no_csfloat_sell == []


def test_missing_fee_for_market_skips_pair():
    """Brakujące prowizje dla danego rynku → para (buy, sell) jest pomijana."""
    prices = {
        "Item X": [
            _make_price_entry("steam", 10.0, quantity=50),
            _make_price_entry("unknown_market", 20.0, quantity=50),
        ]
    }
    fees = _make_fees()  # nie zawiera 'unknown_market'

    opps = _find_arbitrage_opportunities(prices, fees, min_spread_pct=0.0)

    # Żadna okazja z udziałem 'unknown_market'
    unknown_opps = [
        o for o in opps
        if o["details"]["market_buy"] == "unknown_market"
        or o["details"]["market_sell"] == "unknown_market"
    ]
    assert unknown_opps == []


def test_empty_prices_returns_empty():
    """Puste dane wejściowe → brak okazji."""
    opps = _find_arbitrage_opportunities({}, _make_fees(), min_spread_pct=5.0)
    assert opps == []


def test_single_market_no_arbitrage():
    """Tylko jeden rynek dla itemu → żadna para do porównania."""
    prices = {
        "Single Market Item": [
            _make_price_entry("steam", 10.0, quantity=100),
        ]
    }
    opps = _find_arbitrage_opportunities(prices, _make_fees(), min_spread_pct=0.0)
    assert opps == []


def test_multiple_items_multiple_opportunities():
    """Kilka itemów → okazje wykrywane dla każdego z nich osobno."""
    prices = {
        "Item A": [
            _make_price_entry("steam", 10.0, quantity=100),
            _make_price_entry("csfloat", 15.0, quantity=50),
        ],
        "Item B": [
            _make_price_entry("steam", 20.0, quantity=100),
            _make_price_entry("csfloat", 30.0, quantity=50),
        ],
    }
    fees = _make_fees()

    opps = _find_arbitrage_opportunities(prices, fees, min_spread_pct=5.0)

    items_with_opps = {o["market_hash_name"] for o in opps}
    assert "Item A" in items_with_opps
    assert "Item B" in items_with_opps


def test_arbitrage_details_structure():
    """Szczegóły okazji powinny zawierać wszystkie wymagane pola."""
    prices = {
        "Detailed Item": [
            _make_price_entry("steam", 8.0, quantity=200),
            _make_price_entry("csfloat", 11.0, quantity=50),
        ]
    }
    fees = _make_fees()

    opps = _find_arbitrage_opportunities(prices, fees, min_spread_pct=1.0)

    steam_to_csfloat = [
        o for o in opps
        if o["details"]["market_buy"] == "steam" and o["details"]["market_sell"] == "csfloat"
    ]
    assert len(steam_to_csfloat) == 1
    details = steam_to_csfloat[0]["details"]

    required_keys = {
        "market_buy", "price_buy_raw", "source_buy", "buyer_fee", "cost",
        "market_sell", "price_sell_raw", "source_sell", "seller_fee", "revenue",
        "spread_pct", "quantity_sell",
    }
    assert required_keys.issubset(details.keys())


def test_cost_zero_is_skipped():
    """Cena kupna równa 0 → podział przez zero → para pomijana."""
    prices = {
        "Free Item": [
            _make_price_entry("steam", 0.0, quantity=100),
            _make_price_entry("csfloat", 10.0, quantity=50),
        ]
    }
    fees = _make_fees()

    # Nie powinno rzucić wyjątku i nie powinno generować okazji z buy_price=0
    opps = _find_arbitrage_opportunities(prices, fees, min_spread_pct=0.0)
    zero_cost_opps = [o for o in opps if o["details"]["market_buy"] == "steam"
                      and o["details"]["cost"] == 0]
    assert zero_cost_opps == []


def test_three_markets_all_pairs_evaluated():
    """Przy trzech rynkach funkcja sprawdza wszystkie kombinacje par."""
    prices = {
        "Multi Market Item": [
            _make_price_entry("steam", 10.0, quantity=100),
            _make_price_entry("skinport", 11.0, quantity=50),
            _make_price_entry("csfloat", 13.0, quantity=30),
        ]
    }
    fees = _make_fees()

    # min_spread_pct = 0 → wszystkie pary z dodatnim realnym spreadem
    opps = _find_arbitrage_opportunities(prices, fees, min_spread_pct=0.0)

    buy_sell_pairs = {
        (o["details"]["market_buy"], o["details"]["market_sell"]) for o in opps
    }
    # Powinny być sprawdzone przynajmniej pary buy_steam -> sell_csfloat
    assert ("steam", "csfloat") in buy_sell_pairs
