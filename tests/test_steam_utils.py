"""
Testy dla shared/steam.py — funkcja resolve_steam_id.
"""

import pytest

from shared.steam import resolve_steam_id


def test_resolve_direct_steam_id64():
    """Bezpośrednie SteamID64 powinno zostać rozpoznane bez modyfikacji."""
    assert resolve_steam_id("76561198000000000") == "76561198000000000"


def test_resolve_another_valid_id64():
    """Inne prawidłowe SteamID64."""
    assert resolve_steam_id("76561197960287930") == "76561197960287930"


def test_resolve_profiles_url():
    """URL z /profiles/<ID64> powinien zwracać ID64."""
    url = "https://steamcommunity.com/profiles/76561198000000000"
    assert resolve_steam_id(url) == "76561198000000000"


def test_resolve_profiles_url_with_trailing_slash():
    """URL z trailing slash — powinien poprawnie wyciągać ID."""
    url = "https://steamcommunity.com/profiles/76561198000000000/"
    assert resolve_steam_id(url) == "76561198000000000"


def test_resolve_id64_embedded_in_text():
    """SteamID64 wbudowany w dłuższy ciąg tekstu."""
    assert resolve_steam_id("User: 76561198000000000 is online") == "76561198000000000"


def test_resolve_empty_string():
    """Pusty ciąg znaków powinien zwracać None."""
    assert resolve_steam_id("") is None


def test_resolve_none_input():
    """None jako wejście powinno zwracać None."""
    assert resolve_steam_id(None) is None


def test_resolve_no_match_random_text():
    """Losowy tekst bez SteamID powinien zwracać None."""
    assert resolve_steam_id("not_a_steam_id") is None


def test_resolve_no_match_partial_id():
    """Zbyt krótkie ID nie pasuje do wzorca."""
    assert resolve_steam_id("76561198") is None


def test_resolve_vanity_url_no_match():
    """Vanity URL (np. /id/username) nie zawiera ID64 — powinien zwracać None."""
    assert resolve_steam_id("https://steamcommunity.com/id/gaben") is None


def test_resolve_strips_leading_trailing_slashes():
    """Funkcja usuwa slash z początku/końca przed parsowaniem."""
    # strip("/") usuwa obramowujące ukośniki
    url = "/profiles/76561198000000000/"
    result = resolve_steam_id(url)
    assert result == "76561198000000000"


@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("76561198000000001", "76561198000000001"),
        ("https://steamcommunity.com/profiles/76561197960287930", "76561197960287930"),
        ("", None),
        (None, None),
        ("random", None),
    ],
)
def test_resolve_parametrized(input_str, expected):
    """Parametryzowane testy dla różnych wejść."""
    assert resolve_steam_id(input_str) == expected
