# discord_bot

Moduł **bota Discord** — warstwa prezentacji i komunikacji (rola **Konsumenta** w wzorcu Producent–Konsument).

## Zadania
- Nasłuchiwanie nowych alertów w tabeli bazy danych PostgreSQL.
- Wysyłanie powiadomień o wykrytych okazjach do kanału Discord w czasie rzeczywistym.
- Rozdzielenie logiki wysyłkowej od silnika analitycznego — awaria API Discord nie wpływa na ciągłość analizy.

## Technologie
- Python 3.12
- `discord.py` — integracja z Discord API
- `psycopg2` — odczyt alertów z PostgreSQL
