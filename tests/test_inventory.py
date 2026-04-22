"""
Testy dla serwisu inventory (inventory/main.py):
  _parse_inventory_items  — parsowanie odpowiedzi JSON Steam Community Inventory
  _fetch_inventory_json   — pobieranie danych z Steam (async, mockowany aiohttp)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import aiohttp

from inventory.main import _fetch_inventory_json, _parse_inventory_items

# ---------------------------------------------------------------------------
# _parse_inventory_items
# ---------------------------------------------------------------------------


def _make_data(assets: list[dict], descriptions: list[dict]) -> dict:
    return {"assets": assets, "descriptions": descriptions}


def test_parse_empty_assets():
    """Puste pole assets → pusta lista przedmiotów."""
    data = _make_data([], [])
    result = _parse_inventory_items(data, "76561198000000000", "test")
    assert result == []


def test_parse_valid_marketable_items():
    """Poprawne, sprzedawalne przedmioty → lista ze wszystkimi polami."""
    data = _make_data(
        assets=[
            {"classid": "1", "instanceid": "0", "assetid": "AAA", "amount": "2"},
        ],
        descriptions=[
            {
                "classid": "1",
                "instanceid": "0",
                "marketable": 1,
                "market_hash_name": "AK-47 | Redline (Field-Tested)",
            }
        ],
    )
    result = _parse_inventory_items(data, "76561198000000000", "test")
    assert len(result) == 1
    item = result[0]
    assert item["market_hash_name"] == "AK-47 | Redline (Field-Tested)"
    assert item["asset_id"] == "AAA"
    assert item["amount"] == 2


def test_parse_filters_non_marketable():
    """Przedmioty z marketable=0 powinny być odfiltrowane."""
    data = _make_data(
        assets=[
            {"classid": "1", "instanceid": "0", "assetid": "BBB", "amount": "1"},
        ],
        descriptions=[
            {
                "classid": "1",
                "instanceid": "0",
                "marketable": 0,  # niemożliwy do sprzedaży
                "market_hash_name": "Case Key",
            }
        ],
    )
    result = _parse_inventory_items(data, "76561198000000000", "test")
    assert result == []


def test_parse_skips_item_without_asset_id():
    """Przedmiot bez assetid → pomijany."""
    data = _make_data(
        assets=[
            {"classid": "2", "instanceid": "0", "assetid": "", "amount": "1"},
        ],
        descriptions=[
            {
                "classid": "2",
                "instanceid": "0",
                "marketable": 1,
                "market_hash_name": "Glock-18 | Fade",
            }
        ],
    )
    result = _parse_inventory_items(data, "76561198000000000", "test")
    assert result == []


def test_parse_invalid_amount_defaults_to_1():
    """Nieprawidłowe pole amount → domyślna wartość 1."""
    data = _make_data(
        assets=[
            {"classid": "3", "instanceid": "0", "assetid": "CCC", "amount": "invalid"},
        ],
        descriptions=[
            {
                "classid": "3",
                "instanceid": "0",
                "marketable": 1,
                "market_hash_name": "AWP | Asiimov",
            }
        ],
    )
    result = _parse_inventory_items(data, "76561198000000000", "test")
    assert len(result) == 1
    assert result[0]["amount"] == 1


def test_parse_missing_description_skips_asset():
    """Brak opisu do danego classid/instanceid → asset pomijany."""
    data = _make_data(
        assets=[
            {"classid": "99", "instanceid": "0", "assetid": "ZZZ", "amount": "1"},
        ],
        descriptions=[],  # brak opisu
    )
    result = _parse_inventory_items(data, "76561198000000000", "test")
    assert result == []


def test_parse_multiple_items():
    """Kilka przedmiotów → lista ze wszystkimi."""
    data = _make_data(
        assets=[
            {"classid": "1", "instanceid": "0", "assetid": "A1", "amount": "1"},
            {"classid": "2", "instanceid": "0", "assetid": "A2", "amount": "3"},
        ],
        descriptions=[
            {"classid": "1", "instanceid": "0", "marketable": 1, "market_hash_name": "Item A"},
            {"classid": "2", "instanceid": "0", "marketable": 1, "market_hash_name": "Item B"},
        ],
    )
    result = _parse_inventory_items(data, "76561198000000000", "test")
    assert len(result) == 2
    names = {i["market_hash_name"] for i in result}
    assert names == {"Item A", "Item B"}


# ---------------------------------------------------------------------------
# _fetch_inventory_json
# ---------------------------------------------------------------------------


class _MockResp:
    def __init__(self, status: int, json_data=None, text_data: str = "error"):
        self.status = status
        self._json_data = json_data
        self._text_data = text_data

    async def json(self, content_type=None):
        return self._json_data

    async def text(self):
        return self._text_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


async def test_fetch_json_200_returns_dict():
    """Odpowiedź 200 z poprawnym JSON → zwraca słownik."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = _MockResp(200, {"assets": [], "descriptions": []})

    result = await _fetch_inventory_json(
        session,
        "http://example.com",
        steam_id64="76561198000000000",
        source="test",
        headers={},
        params={},
    )
    assert result == {"assets": [], "descriptions": []}


async def test_fetch_json_429_returns_none():
    """Status 429 (rate limit) → None."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = _MockResp(429)

    result = await _fetch_inventory_json(
        session,
        "http://example.com",
        steam_id64="76561198000000000",
        source="test",
        headers={},
        params={},
    )
    assert result is None


async def test_fetch_json_non_200_returns_none():
    """Status 403 → None (błąd po stronie API)."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = _MockResp(403, text_data="Forbidden")

    result = await _fetch_inventory_json(
        session,
        "http://example.com",
        steam_id64="76561198000000000",
        source="test",
        headers={},
        params={},
    )
    assert result is None


async def test_fetch_json_exception_returns_none():
    """Wyjątek sieci (np. timeout) → None."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.side_effect = aiohttp.ClientConnectionError("timeout")

    result = await _fetch_inventory_json(
        session,
        "http://example.com",
        steam_id64="76561198000000000",
        source="test",
        headers={},
        params={},
    )
    assert result is None


async def test_fetch_json_non_dict_response_returns_none():
    """Odpowiedź 200, ale JSON to lista (nie słownik) → None."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = _MockResp(200, ["not", "a", "dict"])

    result = await _fetch_inventory_json(
        session,
        "http://example.com",
        steam_id64="76561198000000000",
        source="test",
        headers={},
        params={},
    )
    assert result is None
