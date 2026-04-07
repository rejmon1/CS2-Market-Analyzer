"""
Konfiguracja logowania używana przez wszystkie serwisy.

Użycie:
    from shared.logger import get_logger
    logger = get_logger(__name__)
"""
import logging
import os

_configured = False


def get_logger(name: str) -> logging.Logger:
    """
    Zwraca logger z ujednoliconym formatem.
    Poziom logowania kontrolowany przez zmienną środowiskową LOG_LEVEL
    (domyślnie INFO).
    """
    global _configured
    if not _configured:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        _configured = True
    return logging.getLogger(name)
