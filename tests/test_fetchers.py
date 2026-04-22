"""
Testy jednostkowe dla konkretnych fetcherów rynkowych:
  - SteamFetcher  (fetchers/steam.py)
  - SkinportFetcher (fetchers/skinport.py)
  - CSFloatFetcher  (fetchers/csfloat.py)

Każdy test mockuje sesję aiohttp i weryfikuje:
- parsowanie odpowiedzi API → lista PriceRecord
- obsługę brakujących cen
- nieoczekiwany format odpowiedzi
- brak dopasowań do listy śledzonych itemów
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fetchers.csfloat import CSFloatFetcher
from fetchers.skinport import SkinportFetcher
from fetchers.steam import SteamFetcher

# ---------------------------------------------------------------------------
# Pomocnicza klasa — mock odpowiedzi HTTP
# ---------------------------------------------------------------------------


class _MockResponse:
    def __init__(self, status: int, json_data=None, headers: dict | None = None):
        self.status = status
        self._json_data = json_data
        self.headers = headers or {}

    async def json(self, content_type=None):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def raise_for_status(self):
        pass


# ---------------------------------------------------------------------------
# SteamFetcher
# ---------------------------------------------------------------------------


@pytest.fixture
def steam_session():
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def steam_fetcher(steam_session):
    return SteamFetcher(steam_session, api_key="test_key")


async def test_steam_fetch_returns_price_records(steam_fetcher):
    """Poprawna odpowiedź Steam API → lista PriceRecord z poprawnymi danymi."""
    api_response = {
        "data": [
            {
                "market_hash_name": "AK-47 | Redline (Field-Tested)",
                "prices": {
                    "latest": 12.50,
                    "sold": {"last_7d": 42},
                },
            },
            {
                "market_hash_name": "AWP | Asiimov (Field-Tested)",
                "prices": {
                    "latest": 35.00,
                    "sold": {"last_7d": 10},
                },
            },
        ]
    }
    steam_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await steam_fetcher.fetch(
            ["AK-47 | Redline (Field-Tested)", "AWP | Asiimov (Field-Tested)"]
        )

    assert len(records) == 2
    ak = next(r for r in records if "AK-47" in r.market_hash_name)
    assert ak.lowest_price == 12.50
    assert ak.quantity == 42
    assert ak.market == "steam"


async def test_steam_fetch_filters_untracked_items(steam_fetcher):
    """Przedmioty spoza listy śledzonych powinny być pominięte."""
    api_response = {
        "data": [
            {"market_hash_name": "AK-47 | Redline (Field-Tested)", "prices": {"latest": 10.0}},
            {"market_hash_name": "Untracked Item", "prices": {"latest": 5.0}},
        ]
    }
    steam_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await steam_fetcher.fetch(["AK-47 | Redline (Field-Tested)"])

    assert len(records) == 1
    assert records[0].market_hash_name == "AK-47 | Redline (Field-Tested)"


async def test_steam_fetch_skips_item_without_latest_price(steam_fetcher):
    """Przedmiot bez pola 'latest' w cenach powinien być pominięty."""
    api_response = {
        "data": [
            {
                "market_hash_name": "AK-47 | Redline (Field-Tested)",
                "prices": {"safe": 10.0},  # brak 'latest'
            }
        ]
    }
    steam_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await steam_fetcher.fetch(["AK-47 | Redline (Field-Tested)"])

    assert records == []


async def test_steam_fetch_unexpected_response_structure(steam_fetcher):
    """Odpowiedź bez klucza 'data' → pusta lista."""
    steam_fetcher.session.get.return_value = _MockResponse(200, {"error": "invalid"})

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await steam_fetcher.fetch(["AK-47 | Redline (Field-Tested)"])

    assert records == []


async def test_steam_fetch_api_error_returns_empty(steam_fetcher):
    """Błąd sieciowy w _get (RuntimeError po wyczerpaniu prób) → pusta lista."""
    steam_fetcher.session.get.side_effect = [_MockResponse(500)] * SteamFetcher.MAX_RETRIES

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await steam_fetcher.fetch(["AK-47 | Redline (Field-Tested)"])

    assert records == []


async def test_steam_fetch_zero_quantity_when_sold_missing(steam_fetcher):
    """Brak pola 'sold' → quantity=0."""
    api_response = {
        "data": [
            {
                "market_hash_name": "Karambit | Fade (Factory New)",
                "prices": {"latest": 800.0},  # brak 'sold'
            }
        ]
    }
    steam_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await steam_fetcher.fetch(["Karambit | Fade (Factory New)"])

    assert len(records) == 1
    assert records[0].quantity == 0


async def test_steam_fetch_tags_price_source(steam_fetcher):
    """Pole _price_source w raw_data powinno być ustawione na 'latest'."""
    api_response = {
        "data": [
            {
                "market_hash_name": "M4A4 | Howl (Factory New)",
                "prices": {"latest": 2000.0, "sold": {"last_7d": 1}},
            }
        ]
    }
    steam_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await steam_fetcher.fetch(["M4A4 | Howl (Factory New)"])

    assert records[0].raw_data["_price_source"] == "latest"


# ---------------------------------------------------------------------------
# SkinportFetcher
# ---------------------------------------------------------------------------


@pytest.fixture
def skinport_session():
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def skinport_fetcher(skinport_session):
    return SkinportFetcher(skinport_session, client_id="my_id", client_secret="my_secret")


def test_skinport_auth_header_is_basic(skinport_fetcher):
    """Nagłówek autoryzacji powinien być zakodowanym Base64 'Basic <credentials>'."""
    expected_credentials = base64.b64encode(b"my_id:my_secret").decode()
    assert skinport_fetcher._auth_header == f"Basic {expected_credentials}"


async def test_skinport_fetch_returns_price_records(skinport_fetcher):
    """Poprawna odpowiedź Skinport API → lista PriceRecord."""
    api_response = [
        {
            "market_hash_name": "AWP | Asiimov (Field-Tested)",
            "min_price": 28.50,
            "quantity": 15,
        }
    ]
    skinport_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await skinport_fetcher.fetch(["AWP | Asiimov (Field-Tested)"])

    assert len(records) == 1
    assert records[0].market_hash_name == "AWP | Asiimov (Field-Tested)"
    assert records[0].lowest_price == 28.50
    assert records[0].quantity == 15
    assert records[0].market == "skinport"


async def test_skinport_fetch_fallback_to_min_tradable_price(skinport_fetcher):
    """Gdy min_price jest None, fallback do min_tradable_price."""
    api_response = [
        {
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "min_price": None,
            "min_tradable_price": 11.00,
            "quantity": 5,
        }
    ]
    skinport_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await skinport_fetcher.fetch(["AK-47 | Redline (Field-Tested)"])

    assert len(records) == 1
    assert records[0].lowest_price == 11.00
    assert records[0].raw_data["_price_source"] == "min_tradable_price"


async def test_skinport_fetch_skips_item_no_price(skinport_fetcher):
    """Przedmiot bez żadnej ceny (min_price=None, min_tradable_price=None) → pominięty."""
    api_response = [
        {
            "market_hash_name": "Rare Item",
            "min_price": None,
            "min_tradable_price": None,
            "quantity": 1,
        }
    ]
    skinport_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await skinport_fetcher.fetch(["Rare Item"])

    assert records == []


async def test_skinport_fetch_unexpected_response_not_list(skinport_fetcher):
    """Odpowiedź nie będąca listą → pusta lista rekordów."""
    skinport_fetcher.session.get.return_value = _MockResponse(200, {"error": "bad"})

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await skinport_fetcher.fetch(["AK-47 | Redline (Field-Tested)"])

    assert records == []


async def test_skinport_fetch_tags_min_price_source(skinport_fetcher):
    """Gdy min_price jest dostępny, _price_source = 'min_price'."""
    api_response = [
        {
            "market_hash_name": "Glock-18 | Fade (Factory New)",
            "min_price": 150.0,
            "quantity": 3,
        }
    ]
    skinport_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await skinport_fetcher.fetch(["Glock-18 | Fade (Factory New)"])

    assert records[0].raw_data["_price_source"] == "min_price"


async def test_skinport_fetch_filters_untracked_items(skinport_fetcher):
    """Elementy spoza listy śledzonych powinny być odfiltrowane."""
    api_response = [
        {"market_hash_name": "Known Item", "min_price": 5.0, "quantity": 10},
        {"market_hash_name": "Unknown Item", "min_price": 3.0, "quantity": 20},
    ]
    skinport_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await skinport_fetcher.fetch(["Known Item"])

    assert len(records) == 1
    assert records[0].market_hash_name == "Known Item"


# ---------------------------------------------------------------------------
# CSFloatFetcher
# ---------------------------------------------------------------------------


@pytest.fixture
def csfloat_session():
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def csfloat_fetcher(csfloat_session):
    return CSFloatFetcher(csfloat_session, api_key="csfloat_test_key")


async def test_csfloat_fetch_returns_price_records(csfloat_fetcher):
    """Poprawna odpowiedź CSFloat API → lista PriceRecord z ceną w USD."""
    api_response = [
        {
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "min_price": 1050,  # centy → 10.50 USD
            "quantity": 25,
        }
    ]
    csfloat_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await csfloat_fetcher.fetch(["AK-47 | Redline (Field-Tested)"])

    assert len(records) == 1
    assert records[0].market_hash_name == "AK-47 | Redline (Field-Tested)"
    assert records[0].lowest_price == pytest.approx(10.50, abs=1e-4)
    assert records[0].quantity == 25
    assert records[0].market == "csfloat"


async def test_csfloat_fetch_converts_cents_to_usd(csfloat_fetcher):
    """Cena w centach (np. 7150) powinna być przeliczona na USD (71.50)."""
    api_response = [
        {
            "market_hash_name": "AWP | Dragon Lore (Factory New)",
            "min_price": 150000,  # 1500.00 USD
            "quantity": 1,
        }
    ]
    csfloat_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await csfloat_fetcher.fetch(["AWP | Dragon Lore (Factory New)"])

    assert records[0].lowest_price == pytest.approx(1500.0, abs=1e-4)


async def test_csfloat_fetch_filters_untracked_items(csfloat_fetcher):
    """Elementy spoza listy śledzonych powinny być odfiltrowane."""
    api_response = [
        {"market_hash_name": "Tracked Item", "min_price": 500, "quantity": 3},
        {"market_hash_name": "Not Tracked", "min_price": 200, "quantity": 10},
    ]
    csfloat_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await csfloat_fetcher.fetch(["Tracked Item"])

    assert len(records) == 1
    assert records[0].market_hash_name == "Tracked Item"


async def test_csfloat_fetch_skips_item_without_price(csfloat_fetcher):
    """Przedmiot z min_price=None powinien być pominięty."""
    api_response = [{"market_hash_name": "Mystery Item", "min_price": None, "quantity": 5}]
    csfloat_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await csfloat_fetcher.fetch(["Mystery Item"])

    assert records == []


async def test_csfloat_fetch_unexpected_response_not_list(csfloat_fetcher):
    """Odpowiedź nie będąca listą → pusta lista rekordów."""
    csfloat_fetcher.session.get.return_value = _MockResponse(200, {"data": []})

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await csfloat_fetcher.fetch(["AK-47 | Redline (Field-Tested)"])

    assert records == []


async def test_csfloat_fetch_tags_price_source(csfloat_fetcher):
    """Pole _price_source w raw_data powinno być ustawione na 'min_price'."""
    api_response = [
        {"market_hash_name": "Karambit | Fade (Factory New)", "min_price": 80000, "quantity": 2}
    ]
    csfloat_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await csfloat_fetcher.fetch(["Karambit | Fade (Factory New)"])

    assert records[0].raw_data["_price_source"] == "min_price"


async def test_csfloat_fetch_zero_quantity_fallback(csfloat_fetcher):
    """Brak pola 'quantity' → quantity=0."""
    api_response = [{"market_hash_name": "AK-47 | Redline (Field-Tested)", "min_price": 1000}]
    csfloat_fetcher.session.get.return_value = _MockResponse(200, api_response)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        records = await csfloat_fetcher.fetch(["AK-47 | Redline (Field-Tested)"])

    assert records[0].quantity == 0
