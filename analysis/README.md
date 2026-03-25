# analysis

Moduł **silnika analitycznego** — serce systemu wykrywającego okazje rynkowe.

## Zadania
- Analiza zebranych danych cenowych z bazy danych.
- Wykrywanie okazji arbitrażowych (porównywanie cen tego samego przedmiotu na różnych rynkach za pomocą SQL JOIN).
- Wykrywanie anomalii wolumenowych (Pump & Dump) na podstawie historii cen.
- Zapisywanie wyników analizy jako „alerty" w bazie danych (rola **Producenta** w wzorcu Producent–Konsument).

## Technologie
- Python 3.12
- `psycopg2` — zapytania analityczne do PostgreSQL
