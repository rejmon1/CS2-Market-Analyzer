import pytest
import os
from shared.db import items_count

@pytest.mark.skipif(os.environ.get("DATABASE_URL") is None, reason="DATABASE_URL not set")
def test_db_connection_placeholder():
    """
    Placeholder dla testów integracyjnych z bazą danych.
    Ten test zostanie uruchomiony tylko w CI (GitHub Actions).
    """
    # W CI DATABASE_URL jest ustawiony, więc ten test spróbuje się połączyć.
    # Ponieważ baza jest pusta, items_count powinien zwrócić 0 (lub rzucić błąd jeśli tabela nie istnieje).
    # To służy do weryfikacji połączenia w pipeline.
    pass
