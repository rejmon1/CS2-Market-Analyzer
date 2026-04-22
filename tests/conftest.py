"""
Konfiguracja globalna dla testów.
Mockuje psycopg2, który nie jest instalowany w środowisku testowym,
ale jest importowany przez shared/db.py i analysis/main.py.
"""

import sys
from unittest.mock import MagicMock

# Psycopg2 nie jest zainstalowany w środowisku testów jednostkowych —
# mockujemy go, żeby import shared.db i analysis.main nie powodował błędu.
sys.modules.setdefault("psycopg2", MagicMock())
sys.modules.setdefault("psycopg2.extras", MagicMock())
