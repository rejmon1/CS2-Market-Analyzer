# shared

Moduł **wspólnego kodu** współdzielonego przez wszystkie serwisy.

## Zawartość
- Modele danych (np. dataclasses / Pydantic schemas reprezentujące przedmioty, ceny, alerty).
- Walidacje wejściowych danych z API.
- Helpery i narzędzia (np. obsługa połączeń z bazą, logger, konfiguracja).

## Uwagi
Kod z tego modułu jest importowany przez pozostałe serwisy.
Zmiany tutaj mogą wpływać na wszystkie usługi — wprowadzaj je ostrożnie.
