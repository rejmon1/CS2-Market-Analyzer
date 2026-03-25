# ingestion

Moduł odpowiedzialny za **pobieranie i zbieranie danych rynkowych** z zewnętrznych API (Steam Community Market, Skinport i inne).

## Zadania
- Cykliczne odpytywanie API rynków CS2 o aktualne ceny przedmiotów.
- Zapis surowych odpowiedzi (format JSONB) do bazy danych PostgreSQL.
- Obsługa wielu rynków w ramach jednego serwisu (MVP — zapobiega nadmiernemu rozrostowi infrastruktury).

## Technologie
- Python 3.12
- `requests` / `aiohttp` — zapytania HTTP
- `psycopg2` — połączenie z PostgreSQL
