"""
Konfiguracja serwisu inventory.
"""
import os


def get_poll_interval() -> int:
    """Interwał między okresowym odświeżaniem ekwipunków wszystkich graczy."""
    return int(os.environ.get("INVENTORY_POLL_INTERVAL", "3600"))


def get_steam_inventory_url(steam_id64: str) -> str:
    """Zwraca publiczny URL do JSON-a ekwipunku Steam dla CS2."""
    # Używamy najprostszego formatu, aby uniknąć błędu 400
    return f"https://steamcommunity.com/inventory/{steam_id64}/730/2"
