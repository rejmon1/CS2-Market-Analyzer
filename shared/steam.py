import re
from typing import Optional

# Regexy do wyciągania SteamID64
RE_STEAM_ID64 = re.compile(r"7656119[0-9]{10}")
RE_PROFILES_LINK = re.compile(r"profiles/([0-9]{17})")


def resolve_steam_id(input_str: str | None) -> Optional[str]:
    """Wyciąga SteamID64 z linku lub ciągu znaków."""
    if not input_str:
        return None

    input_str = input_str.strip("/")

    # 1. Czyste ID64
    match = RE_STEAM_ID64.search(input_str)
    if match:
        return match.group(0)

    # 2. Link /profiles/
    match = RE_PROFILES_LINK.search(input_str)
    if match:
        return match.group(0)

    return None
