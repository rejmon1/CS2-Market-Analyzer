"""
Testy dla fetchers/base.py — klasa BaseFetcher i metoda _get().

Testuje:
- Poprawna odpowiedź 200 → zwraca JSON
- Status 429 (rate-limit) → czeka Retry-After sekund i powtarza
- Status 5xx (błąd serwera) → powtarza z backoffem
- aiohttp.ClientError → powtarza z backoffem
- Wyczerpanie wszystkich prób → RuntimeError
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from fetchers.base import BaseFetcher
from shared.models import PriceRecord


# ---------------------------------------------------------------------------
# Pomocnicza klasa — minimalna konkretna implementacja BaseFetcher
# ---------------------------------------------------------------------------


class _StubFetcher(BaseFetcher):
    MARKET_NAME = "stub"

    async def fetch(self, items: list[str]) -> list[PriceRecord]:
        return []


# ---------------------------------------------------------------------------
# Pomocnicza klasa — mock odpowiedzi HTTP aiohttp
# ---------------------------------------------------------------------------


class _MockResponse:
    """Symuluje aiohttp.ClientResponse jako async context manager."""

    def __init__(self, status: int, json_data=None, headers: dict | None = None):
        self.status = status
        self._json_data = json_data or {}
        self.headers = headers or {}

    async def json(self, content_type=None):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=self.status,
            )


# ---------------------------------------------------------------------------
# Testy
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Zwraca mockowaną sesję aiohttp."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def fetcher(mock_session):
    """Zwraca instancję StubFetcher z mockowaną sesją."""
    return _StubFetcher(mock_session)


async def test_get_success_200(fetcher):
    """Odpowiedź 200 powinna zwrócić sparsowany JSON."""
    expected = {"key": "value"}
    resp = _MockResponse(200, expected)
    fetcher.session.get.return_value = resp

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await fetcher._get("http://example.com/api")

    assert result == expected


async def test_get_passes_kwargs_to_session(fetcher):
    """_get przekazuje dodatkowe kwargs (params, headers) do session.get."""
    resp = _MockResponse(200, {"ok": True})
    fetcher.session.get.return_value = resp

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await fetcher._get("http://example.com/api", params={"key": "abc"}, headers={"X": "Y"})

    fetcher.session.get.assert_called_once_with(
        "http://example.com/api",
        params={"key": "abc"},
        headers={"X": "Y"},
    )


async def test_get_retries_on_500(fetcher):
    """Odpowiedź 5xx powinna wyzwolić retry z backoffem; po sukcesie zwraca dane."""
    resp_500 = _MockResponse(500)
    resp_200 = _MockResponse(200, {"result": "ok"})
    fetcher.session.get.side_effect = [resp_500, resp_200]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await fetcher._get("http://example.com/api")

    assert result == {"result": "ok"}
    # Powinien spać po pierwszej nieudanej próbie
    assert mock_sleep.called


async def test_get_rate_limited_429_then_success(fetcher):
    """429 → czeka Retry-After sekund, następna próba zwraca 200."""
    resp_429 = _MockResponse(429, headers={"Retry-After": "30"})
    resp_200 = _MockResponse(200, {"items": []})
    fetcher.session.get.side_effect = [resp_429, resp_200]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await fetcher._get("http://example.com/api")

    assert result == {"items": []}
    # Powinien spać przez Retry-After = 30 s
    mock_sleep.assert_any_call(30.0)


async def test_get_429_default_retry_after(fetcher):
    """429 bez nagłówka Retry-After — domyślne czekanie 60 s."""
    resp_429 = _MockResponse(429, headers={})
    resp_200 = _MockResponse(200, {})
    fetcher.session.get.side_effect = [resp_429, resp_200]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await fetcher._get("http://example.com/api")

    mock_sleep.assert_any_call(60.0)


async def test_get_raises_after_max_retries_on_500(fetcher):
    """Po wyczerpaniu MAX_RETRIES prób (tylko 500) powinien rzucić RuntimeError."""
    resp_500 = _MockResponse(500)
    fetcher.session.get.side_effect = [resp_500] * BaseFetcher.MAX_RETRIES

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RuntimeError, match="Failed to fetch"):
            await fetcher._get("http://example.com/api")


async def test_get_client_error_retries(fetcher):
    """aiohttp.ClientError powoduje retry; po sukcesie zwraca dane."""
    fetcher.session.get.side_effect = [
        aiohttp.ClientConnectionError("connection refused"),
        _MockResponse(200, {"data": "ok"}),
    ]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await fetcher._get("http://example.com/api")

    assert result == {"data": "ok"}


async def test_get_raises_after_max_retries_on_client_error(fetcher):
    """Po wyczerpaniu MAX_RETRIES przy błędach sieci → RuntimeError."""
    fetcher.session.get.side_effect = [
        aiohttp.ClientConnectionError("timeout"),
    ] * BaseFetcher.MAX_RETRIES

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RuntimeError, match="Failed to fetch"):
            await fetcher._get("http://example.com/api")


async def test_get_respects_rate_limit_until(fetcher):
    """Jeśli _rate_limit_until jest w przyszłości, _get czeka przed wysłaniem żądania."""
    import time

    fetcher._rate_limit_until = time.monotonic() + 10.0  # symulujemy aktywny rate-limit
    resp_200 = _MockResponse(200, {})
    fetcher.session.get.return_value = resp_200

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await fetcher._get("http://example.com/api")

    # Pierwsze wywołanie sleep (oczekiwanie na rate-limit) powinno mieć wartość ~10
    first_sleep_arg = mock_sleep.call_args_list[0][0][0]
    assert 9.0 <= first_sleep_arg <= 10.5


async def test_get_429_updates_rate_limit_until(fetcher):
    """Po 429 pole _rate_limit_until powinno być ustawione na przyszłość."""
    import time

    resp_429 = _MockResponse(429, headers={"Retry-After": "45"})
    resp_200 = _MockResponse(200, {})
    fetcher.session.get.side_effect = [resp_429, resp_200]

    before = time.monotonic()
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await fetcher._get("http://example.com/api")

    # _rate_limit_until powinno być ustawione ~45 sekund od momentu odpowiedzi 429
    assert fetcher._rate_limit_until >= before + 40
