# discord_bot

Moduł **bota Discord** — warstwa prezentacji i komunikacji (rola **Konsumenta** w wzorcu Producent–Konsument).

## Zadania
- Nasłuchiwanie nowych alertów w tabeli bazy danych PostgreSQL.
- Wysyłanie powiadomień o wykrytych okazjach do kanału Discord w czasie rzeczywistym.
- Rozdzielenie logiki wysyłkowej od silnika analitycznego — awaria API Discord nie wpływa na ciągłość analizy.
- Komenda `/inv refresh_prices` odświeża ceny ekwipunku użytkownika na żądanie (Steam Inventory API -> ingestion -> Steam/Skinport/CSFloat).
- Globalna whitelista użytkowników do `/inv refresh_prices` jest zarządzana przez adminów bota (`/admin allow_refresh`, `/admin revoke_refresh`, `/admin list_refresh_access`).
- Komendy personalne `/inv info` oraz `/inv update` działają tylko w DM z botem.

## Technologie
- Python 3.12
- `discord.py` — integracja z Discord API
- `psycopg2` — odczyt alertów z PostgreSQL
