# 7. Testowanie

## 7.1 Strategia testowania

### Poziomy testów

**Testy jednostkowe (Unit Tests)**

Stanowią fundament pokrycia w projekcie. Testowane są:

- `shared/models.py` — struktury danych `PriceRecord`, `Item`, `MarketFee`, `Alert`
- `shared/logger.py` — konfiguracja i zwracanie instancji loggera
- `shared/steam.py` — parsowanie SteamID64 z różnych formatów URL
- `shared/db.py` — testowane w trybie integracyjnym (wymaga `DATABASE_URL`)
- `ingestion/config.py` — odczyt kluczy API i interwałów z ENV
- `ingestion/fetchers/base.py` — mechanizm retry, rate-limiting, logika `GET`
- `ingestion/fetchers/steam.py`, `skinport.py`, `csfloat.py` — parsowanie odpowiedzi API
- `ingestion/scheduler.py` — seedowanie bazy, budowa listy fetcherów, cykl odpytywania
- `analysis/config.py` — odczyt progów arbitrażu z ENV
- `analysis/main.py` — algorytm wykrywania okazji arbitrażowych (`_find_arbitrage_opportunities`)
- `discord_bot/config.py` — parsowanie tokenów, ID kanału, listy adminów z ENV
- `discord_bot/main.py` — formatowanie wiadomości (`_fmt_alert`, `_fmt_price_row`), kontrola uprawnień (`_is_admin_user`)
- `inventory/config.py` — interwały odświeżania i generowanie URL Steam Inventory
- `inventory/main.py` — parsowanie JSON ekwipunku (`_parse_inventory_items`), obsługa błędów HTTP (`_fetch_inventory_json`)

**Uzasadnienie:** Każdy mikroserwis komunikuje się z pozostałymi wyłącznie przez bazę danych. Testy jednostkowe pozwalają weryfikować logikę każdego serwisu niezależnie, bez uruchamiania całego stosu.

---

**Testy integracyjne**

Plik `tests/test_db_placeholder.py` weryfikuje połączenie Python ↔ PostgreSQL z prawdziwą bazą. Test jest warunkowy (`skipif DATABASE_URL is None`) — pomijany lokalnie, wykonywany w środowisku CI gdzie podnoszony jest kontener PostgreSQL. Weryfikuje: działanie `db/init.sql`, istnienie tabel oraz podstawowe operacje CRUD.

**Uzasadnienie:** Warstwa `shared/db.py` (165 instrukcji) obsługuje wszystkie serwisy. Błąd SQL wpływałby na cały system — dlatego testy integracyjne są wymagane w pipeline CI/CD.

---

**Testy End-to-End (E2E)**

Testy E2E nie zostały zaimplementowane w bieżącym etapie. Planowane scenariusze:
- Rejestracja SteamID → pobranie ekwipunku → pojawienie się itemów w bazie
- Dodanie itemu → pojawienie się ceny po cyklu ingestion → wykrycie arbitrażu → wysłanie alertu Discord

---

**Analiza statyczna (Static Analysis)**

| Narzędzie | Zastosowanie | Konfiguracja |
|:---|:---|:---|
| **Ruff** | Linting (błędy logiczne, styl PEP 8, sortowanie importów) | `pyproject.toml` — reguły E, F, B, I |
| **Mypy** | Statyczne sprawdzanie typów | `pyproject.toml` — `check_untyped_defs = true` |

Oba narzędzia uruchamiane są automatycznie w pipeline CI/CD (`.github/workflows/ci.yml`).

---

### Narzędzia testowe

| Narzędzie | Rola | Uzasadnienie |
|:---|:---|:---|
| **pytest** | Framework testowy | Standardowy wybór dla projektów Python; wsparcie dla fixtures, parametryzacji, markerów |
| **pytest-asyncio** | Obsługa testów `async/await` | Mikroserwisy `ingestion` i `inventory` korzystają z `aiohttp` i `asyncio` |
| **pytest-cov** | Raport pokrycia kodu | Generuje `coverage.xml` i wynik terminalowy; integruje się z GitHub Actions |
| **unittest.mock** | Mockowanie zewnętrznych zależności | Izolacja od psycopg2, discord.py, aiohttp bez prawdziwej sieci/bazy |

---

### Konwencje

**Nazewnictwo plików:** `tests/test_<modul>.py`, gdzie `<modul>` odpowiada testowanemu plikowi lub usłudze.

**Nazewnictwo funkcji:** `test_<co_testuje>_<oczekiwany_wynik>`, np. `test_database_url_raises_when_not_set`.

**Lokalizacja:** Wszystkie testy w katalogu `tests/` w korzeniu repozytorium.

**Uruchamianie lokalnie:**
```bash
# Instalacja zależności testowych
pip install pytest pytest-asyncio pytest-cov

# Uruchomienie wszystkich testów
pytest tests/

# Uruchomienie z raportem pokrycia
pytest tests/ --cov=shared --cov=ingestion --cov=analysis --cov=inventory --cov=discord_bot

# Testy integracyjne (wymagają bazy)
DATABASE_URL=postgresql://user:pass@localhost/cs2db pytest tests/
```

---

## 7.2 Wyniki testów

Podsumowanie wyników testów z bieżącego etapu.

| Metryka | Wartość |
|:---|:---|
| **Liczba testów jednostkowych** | 149 |
| **Pokrycie kodu (code coverage)** | 46% (config: 91–100%, modele/logger: 93–100%, fetchery: 94–100%, inventory: 51%, analysis engine: 32%, discord_bot/main: 26%, shared/db: 22%\*) |
| **Testy integracyjne — pass / fail** | 0 / 0 (1 pominięty — brak `DATABASE_URL`; wykonywany w CI) |
| **Znalezione błędy** | Krytyczne: 0, Ważne: 3, Drobne: 3 |
| **Testy E2E — pass / fail** | 0 / 0 (nie zaimplementowane w tym etapie) |

\* `shared/db.py` i `discord_bot/main.py` wymagają odpowiednio: prawdziwej bazy PostgreSQL oraz działającego bota Discord do pełnego pokrycia.

---

## 7.3 Zgłoszone błędy

Lista najważniejszych zgłoszonych błędów z bieżącego etapu.

| ID | Opis | Ważność | Priorytet | Status | Przypisany |
|:---|:---|:---|:---|:---|:---|
| BUG-001 | Błędy importów i nieprawidłowe bloki try-except w pierwszej wersji kodu | Ważny | Wysoki | Naprawiony | — |
| BUG-002 | Naruszenia PEP 8: zbyt długie linie, brak spacji wokół operatorów | Drobny | Średni | Naprawiony | — |
| BUG-003 | Brak pytest i zależności testowych w środowisku CI | Ważny | Wysoki | Naprawiony | — |
| BUG-004 | Błędy w docstringach — brakujące opisy parametrów i zwracanych wartości | Drobny | Niski | Naprawiony | — |
| BUG-005 | Ryzyko typowania (Mypy): nieoznaczone typy w kilku funkcjach | Ważny | Średni | Naprawiony | — |
| BUG-006 | Kolizja `sys.modules["main"]` — `test_analysis_engine.py` ładował `analysis/main.py` pod nazwą `"main"`, przez co `test_discord_bot_helpers.py` importował zły moduł | Ważny | Wysoki | Naprawiony | — |

---

## 7.4 Lista testów

| ID | Typ | Nazwa testu | Co testuje | Oczekiwany wynik | Status |
|:---|:---|:---|:---|:---|:---|
| T-001 | Jednostkowy | `test_database_url_raises_when_not_set` (analysis/config) | Brak `DATABASE_URL` w ENV | `RuntimeError` | Pass |
| T-002 | Jednostkowy | `test_database_url_returns_value` (analysis/config) | Ustawiona `DATABASE_URL` | Zwraca wartość ENV | Pass |
| T-003 | Jednostkowy | `test_analysis_interval_default` | Domyślny interwał analizy | 60 sekund | Pass |
| T-004 | Jednostkowy | `test_analysis_interval_custom` | Niestandardowy interwał z ENV | Wartość z ENV | Pass |
| T-005 | Jednostkowy | `test_min_spread_pct_default` | Domyślny minimalny spread | 5.0% | Pass |
| T-006 | Jednostkowy | `test_min_spread_pct_custom` | Niestandardowy spread z ENV | Wartość z ENV | Pass |
| T-007 | Jednostkowy | `test_min_quantity_default` | Domyślna minimalna ilość | 3 | Pass |
| T-008 | Jednostkowy | `test_min_quantity_custom` | Niestandardowa ilość z ENV | Wartość z ENV | Pass |
| T-009 | Jednostkowy | `test_detects_profitable_arbitrage` | Wykrycie okazji arbitrażowej | Lista z ≥1 okazją | Pass |
| T-010 | Jednostkowy | `test_spread_below_threshold_is_ignored` | Spread poniżej progu | Pusta lista | Pass |
| T-011 | Jednostkowy | `test_quantity_below_min_is_ignored` | Za niski wolumen sprzedaży | Okazja pomijana | Pass |
| T-012 | Jednostkowy | `test_missing_fee_for_market_skips_pair` | Brak prowizji dla rynku | Para (buy, sell) pomijana | Pass |
| T-013 | Jednostkowy | `test_empty_prices_returns_empty` | Puste dane wejściowe | Pusta lista | Pass |
| T-014 | Jednostkowy | `test_single_market_no_arbitrage` | Tylko jeden rynek dla itemu | Pusta lista | Pass |
| T-015 | Jednostkowy | `test_multiple_items_multiple_opportunities` | Kilka itemów naraz | Okazje dla każdego | Pass |
| T-016 | Jednostkowy | `test_arbitrage_details_structure` | Struktura słownika okazji | Wszystkie wymagane pola | Pass |
| T-017 | Jednostkowy | `test_cost_zero_is_skipped` | Cena kupna = 0 (dzielenie przez zero) | Para pomijana, brak wyjątku | Pass |
| T-018 | Jednostkowy | `test_three_markets_all_pairs_evaluated` | Trzy rynki — wszystkie pary | Para `(steam, csfloat)` wykryta | Pass |
| T-019 | Jednostkowy | `test_get_success_200` | Odpowiedź 200 z API | Zwraca JSON | Pass |
| T-020 | Jednostkowy | `test_get_passes_kwargs_to_session` | Przekazywanie parametrów do sesji | Parametry obecne w wywołaniu | Pass |
| T-021 | Jednostkowy | `test_get_retries_on_500` | Automatyczne ponowienie po błędzie 500 | Sukces po ponowieniu | Pass |
| T-022 | Jednostkowy | `test_get_rate_limited_429_then_success` | Rate limit 429, potem sukces | Sukces po odczekaniu | Pass |
| T-023 | Jednostkowy | `test_get_429_default_retry_after` | Brak nagłówka `Retry-After` | Domyślne opóźnienie | Pass |
| T-024 | Jednostkowy | `test_get_raises_after_max_retries_on_500` | Wyczerpanie limitu prób przy 500 | `RuntimeError` | Pass |
| T-025 | Jednostkowy | `test_get_client_error_retries` | Błąd połączenia → ponowienie | Sukces po ponowieniu | Pass |
| T-026 | Jednostkowy | `test_get_raises_after_max_retries_on_client_error` | Wyczerpanie limitu przy błędach sieci | Wyjątek | Pass |
| T-027 | Jednostkowy | `test_get_respects_rate_limit_until` | Blokada do określonego czasu | Brak wywołania przed upływem czasu | Pass |
| T-028 | Jednostkowy | `test_get_429_updates_rate_limit_until` | Aktualizacja znacznika rate-limit | Nowa wartość `rate_limit_until` | Pass |
| T-029 | Integracyjny | `test_db_connection_placeholder` | Połączenie z PostgreSQL | Bez wyjątku | Skip\* |
| T-030 | Jednostkowy | `test_parse_csv_ids_single` | Parsowanie pojedynczego ID | Zbiór `{id}` | Pass |
| T-031 | Jednostkowy | `test_parse_csv_ids_multiple` | Parsowanie listy CSV | Zbiór wszystkich ID | Pass |
| T-032 | Jednostkowy | `test_parse_csv_ids_with_spaces` | Ignorowanie spacji | Poprawny zbiór | Pass |
| T-033 | Jednostkowy | `test_parse_csv_ids_empty_string` | Pusty string | Pusty zbiór | Pass |
| T-034 | Jednostkowy | `test_parse_csv_ids_invalid_raises` | Nieliczbowy token w CSV | `RuntimeError` | Pass |
| T-035 | Jednostkowy | `test_discord_token_raises_when_not_set` | Brak `DISCORD_TOKEN` | `RuntimeError` | Pass |
| T-036 | Jednostkowy | `test_discord_token_returns_value` | Ustawiony token | Zwraca token | Pass |
| T-037 | Jednostkowy | `test_discord_channel_id_none_when_not_set` | Brak `DISCORD_CHANNEL_ID` | `None` | Pass |
| T-038 | Jednostkowy | `test_discord_channel_id_returns_int` | Ustawiony ID kanału | Zwraca `int` | Pass |
| T-039 | Jednostkowy | `test_discord_channel_id_invalid_raises` | Nieliczbowy ID kanału | `RuntimeError` | Pass |
| T-040 | Jednostkowy | `test_alert_poll_interval_default` | Domyślny interwał alertów | 30 sekund | Pass |
| T-041 | Jednostkowy | `test_alert_poll_interval_custom` | Niestandardowy interwał | Wartość z ENV | Pass |
| T-042 | Jednostkowy | `test_alert_poll_interval_invalid_raises` | Nieliczbowy interwał | `RuntimeError` | Pass |
| T-043 | Jednostkowy | `test_admin_user_ids_empty_when_not_set` | Brak listy adminów | Pusty zbiór | Pass |
| T-044 | Jednostkowy | `test_admin_user_ids_returns_set_of_ints` | Lista adminów CSV | Zbiór `int` | Pass |
| T-045 | Jednostkowy | `test_fmt_alert_arbitrage` | Formatowanie alertu arbitrażowego | Nazwy rynków i spread w tekście | Pass |
| T-046 | Jednostkowy | `test_fmt_alert_inventory_value_increase` | Formatowanie wzrostu ekwipunku | Emoji 📈 i `+X%` w tekście | Pass |
| T-047 | Jednostkowy | `test_fmt_alert_inventory_value_decrease` | Formatowanie spadku ekwipunku | Emoji 📉 i `-X%` w tekście | Pass |
| T-048 | Jednostkowy | `test_fmt_alert_unknown_type` | Nieznany typ alertu | Fallback z typem w tekście | Pass |
| T-049 | Jednostkowy | `test_fmt_price_row_steam` | Formatowanie ceny Steam | Cena min i wolumen w tekście | Pass |
| T-050 | Jednostkowy | `test_fmt_price_row_skinport` | Formatowanie ceny Skinport | Cena i ilość ofert w tekście | Pass |
| T-051 | Jednostkowy | `test_fmt_price_row_csfloat` | Formatowanie ceny CSFloat | Konwersja centów na USD w tekście | Pass |
| T-052 | Jednostkowy | `test_is_admin_user_when_in_set` | Sprawdzenie admina — ID w zbiorze | `True` | Pass |
| T-053 | Jednostkowy | `test_is_admin_user_when_not_in_set` | Sprawdzenie admina — ID poza zbiorem | `False` | Pass |
| T-054 | Jednostkowy | `test_is_admin_user_empty_set` | Sprawdzenie admina — pusty zbiór | `False` | Pass |
| T-055 | Jednostkowy | `test_steam_fetch_returns_price_records` | Parsowanie odpowiedzi Steam API | Lista `PriceRecord` | Pass |
| T-056 | Jednostkowy | `test_steam_fetch_filters_untracked_items` | Filtrowanie nieśledzonych itemów | Tylko śledzone w wyniku | Pass |
| T-057 | Jednostkowy | `test_steam_fetch_skips_item_without_latest_price` | Item bez ceny → pomijany | Lista bez danego itemu | Pass |
| T-058 | Jednostkowy | `test_steam_fetch_unexpected_response_structure` | Nieoczekiwana struktura JSON | Pusta lista lub brak wyjątku | Pass |
| T-059 | Jednostkowy | `test_steam_fetch_api_error_returns_empty` | Błąd API Steam | Pusta lista | Pass |
| T-060 | Jednostkowy | `test_steam_fetch_zero_quantity_when_sold_missing` | Brak danych o sprzedaży | `quantity = 0` | Pass |
| T-061 | Jednostkowy | `test_steam_fetch_tags_price_source` | Oznaczenie źródła ceny | `"_price_source"` w `raw_data` | Pass |
| T-062 | Jednostkowy | `test_skinport_auth_header_is_basic` | Nagłówek autoryzacji Skinport | Nagłówek `Authorization: Basic …` | Pass |
| T-063 | Jednostkowy | `test_skinport_fetch_returns_price_records` | Parsowanie odpowiedzi Skinport | Lista `PriceRecord` | Pass |
| T-064 | Jednostkowy | `test_skinport_fetch_fallback_to_min_tradable_price` | Fallback na min. ceny handlowej | `PriceRecord` z ceną fallback | Pass |
| T-065 | Jednostkowy | `test_skinport_fetch_skips_item_no_price` | Item bez ceny → pomijany | Nie ma go na liście | Pass |
| T-066 | Jednostkowy | `test_skinport_fetch_unexpected_response_not_list` | Odpowiedź nie jest listą | Pusta lista | Pass |
| T-067 | Jednostkowy | `test_skinport_fetch_tags_min_price_source` | Oznaczenie źródła ceny Skinport | `"_price_source"` w `raw_data` | Pass |
| T-068 | Jednostkowy | `test_skinport_fetch_filters_untracked_items` | Filtrowanie nieśledzonych | Tylko śledzone w wyniku | Pass |
| T-069 | Jednostkowy | `test_csfloat_fetch_returns_price_records` | Parsowanie odpowiedzi CSFloat | Lista `PriceRecord` | Pass |
| T-070 | Jednostkowy | `test_csfloat_fetch_converts_cents_to_usd` | Konwersja centów na USD | Cena = wartość / 100 | Pass |
| T-071 | Jednostkowy | `test_csfloat_fetch_filters_untracked_items` | Filtrowanie nieśledzonych | Tylko śledzone w wyniku | Pass |
| T-072 | Jednostkowy | `test_csfloat_fetch_skips_item_without_price` | Item bez ceny → pomijany | Nie ma go na liście | Pass |
| T-073 | Jednostkowy | `test_csfloat_fetch_unexpected_response_not_list` | Odpowiedź nie jest listą | Pusta lista | Pass |
| T-074 | Jednostkowy | `test_csfloat_fetch_tags_price_source` | Oznaczenie źródła ceny CSFloat | `"_price_source"` w `raw_data` | Pass |
| T-075 | Jednostkowy | `test_csfloat_fetch_zero_quantity_fallback` | Brak pola ilości | `quantity = 0` | Pass |
| T-076 | Jednostkowy | `test_database_url_raises_when_not_set` (ingestion/config) | Brak `DATABASE_URL` | `RuntimeError` | Pass |
| T-077 | Jednostkowy | `test_database_url_returns_value` (ingestion/config) | Ustawiona `DATABASE_URL` | Zwraca wartość ENV | Pass |
| T-078 | Jednostkowy | `test_poll_interval_steam_default` | Domyślny interwał Steam | 6000 sekund | Pass |
| T-079 | Jednostkowy | `test_poll_interval_steam_custom` | Niestandardowy interwał Steam | Wartość z ENV | Pass |
| T-080 | Jednostkowy | `test_poll_interval_other_market_default` | Domyślny interwał Skinport/CSFloat | 300 sekund | Pass |
| T-081 | Jednostkowy | `test_poll_interval_other_market_custom` | Niestandardowy interwał innych rynków | Wartość z ENV | Pass |
| T-082 | Jednostkowy | `test_steamapis_key_empty_by_default` | Brak klucza Steam API | Pusty string | Pass |
| T-083 | Jednostkowy | `test_steamapis_key_returns_value` | Ustawiony klucz Steam API | Zwraca klucz | Pass |
| T-084 | Jednostkowy | `test_skinport_credentials_empty_by_default` | Brak kredencjałów Skinport | `("", "")` | Pass |
| T-085 | Jednostkowy | `test_skinport_credentials_returns_values` | Ustawione kredencjały Skinport | Krotka z wartościami | Pass |
| T-086 | Jednostkowy | `test_csfloat_api_key_empty_by_default` | Brak klucza CSFloat | Pusty string | Pass |
| T-087 | Jednostkowy | `test_csfloat_api_key_returns_value` | Ustawiony klucz CSFloat | Zwraca klucz | Pass |
| T-088 | Jednostkowy | `test_parse_empty_assets` | Pusta lista assets | Pusta lista itemów | Pass |
| T-089 | Jednostkowy | `test_parse_valid_marketable_items` | Poprawny, sprzedawalny przedmiot | Item z wszystkimi polami | Pass |
| T-090 | Jednostkowy | `test_parse_filters_non_marketable` | Przedmiot z `marketable=0` | Odfiltrowywany | Pass |
| T-091 | Jednostkowy | `test_parse_skips_item_without_asset_id` | Przedmiot bez `assetid` | Pomijany | Pass |
| T-092 | Jednostkowy | `test_parse_invalid_amount_defaults_to_1` | Nieprawidłowe pole `amount` | `amount = 1` | Pass |
| T-093 | Jednostkowy | `test_parse_missing_description_skips_asset` | Brak opisu do danego classid | Asset pomijany | Pass |
| T-094 | Jednostkowy | `test_parse_multiple_items` | Kilka przedmiotów naraz | Lista ze wszystkimi | Pass |
| T-095 | Jednostkowy | `test_fetch_json_200_returns_dict` | Odpowiedź 200 ze Steam | Zwraca słownik JSON | Pass |
| T-096 | Jednostkowy | `test_fetch_json_429_returns_none` | Rate limit 429 | `None` | Pass |
| T-097 | Jednostkowy | `test_fetch_json_non_200_returns_none` | Błąd 403 | `None` | Pass |
| T-098 | Jednostkowy | `test_fetch_json_exception_returns_none` | Wyjątek sieci (timeout) | `None` | Pass |
| T-099 | Jednostkowy | `test_fetch_json_non_dict_response_returns_none` | JSON nie jest słownikiem | `None` | Pass |
| T-100 | Jednostkowy | `test_poll_interval_default` (inventory/config) | Domyślny interwał ekwipunku | 3600 sekund | Pass |
| T-101 | Jednostkowy | `test_poll_interval_custom` (inventory/config) | Niestandardowy interwał | Wartość z ENV | Pass |
| T-102 | Jednostkowy | `test_error_retry_default` | Domyślny backoff po błędzie | 300 sekund | Pass |
| T-103 | Jednostkowy | `test_error_retry_custom` | Niestandardowy backoff | Wartość z ENV | Pass |
| T-104 | Jednostkowy | `test_steam_inventory_url_format` | Format URL ekwipunku | Zawiera SteamID64 i `730/2` | Pass |
| T-105 | Jednostkowy | `test_steam_inventory_url_different_ids` | Różne SteamID → różne URL | URL-e są unikalne | Pass |
| T-106 | Jednostkowy | `test_get_logger_returns_logger_instance` | Zwracanie instancji loggera | Obiekt `logging.Logger` | Pass |
| T-107 | Jednostkowy | `test_get_logger_correct_name` | Poprawna nazwa loggera | `logger.name == podana_nazwa` | Pass |
| T-108 | Jednostkowy | `test_get_logger_same_instance_for_same_name` | Singleton per nazwa | Ten sam obiekt dla tej samej nazwy | Pass |
| T-109 | Jednostkowy | `test_get_logger_different_instances_for_different_names` | Różne instancje dla różnych nazw | Dwa różne obiekty | Pass |
| T-110 | Jednostkowy | `test_get_logger_sets_configured_flag` | Ustawienie flagi konfiguracji | `_configured == True` | Pass |
| T-111 | Jednostkowy | `test_get_logger_respects_log_level_env` | Poziom logowania z ENV | Ustawiony poziom | Pass |
| T-112 | Jednostkowy | `test_get_logger_default_level_is_info` | Domyślny poziom logowania | `INFO` | Pass |
| T-113 | Jednostkowy | `test_get_logger_only_configures_once` | Konfiguracja tylko raz | Handler dodawany jednokrotnie | Pass |
| T-114 | Jednostkowy | `test_price_record_creation` | Tworzenie obiektu `PriceRecord` | Wszystkie pola ustawione | Pass |
| T-115 | Jednostkowy | `test_price_record_default_fetched_at` | Domyślna data pobrania | Czas UTC z `datetime.now` | Pass |
| T-116 | Jednostkowy | `test_price_record_market_field` | Pole `market` w `PriceRecord` | Poprawna wartość | Pass |
| T-117 | Jednostkowy | `test_item_creation` | Tworzenie obiektu `Item` | Wszystkie pola ustawione | Pass |
| T-118 | Jednostkowy | `test_item_added_by` | Pole `added_by` w `Item` | Poprawna wartość | Pass |
| T-119 | Jednostkowy | `test_item_inactive` | Item z `active=False` | `active == False` | Pass |
| T-120 | Jednostkowy | `test_market_fee_creation` | Tworzenie `MarketFee` | Poprawne prowizje | Pass |
| T-121 | Jednostkowy | `test_market_fee_skinport` | Prowizje Skinport | Wartości specyficzne dla Skinport | Pass |
| T-122 | Jednostkowy | `test_market_fee_with_buyer_fee` | Prowizja kupującego | Ustawiona wartość | Pass |
| T-123 | Jednostkowy | `test_alert_creation` | Tworzenie `Alert` | Wszystkie pola ustawione | Pass |
| T-124 | Jednostkowy | `test_alert_sent_flag` | Flaga `sent` w `Alert` | Domyślnie `False` | Pass |
| T-125 | Jednostkowy | `test_alert_no_item_id` | Alert bez `item_id` | `item_id == None` | Pass |
| T-126 | Jednostkowy | `test_seed_if_empty_skips_when_items_exist` | Seedowanie gdy tabela niepusta | `seed_items` nie wywołane | Pass |
| T-127 | Jednostkowy | `test_seed_if_empty_seeds_when_empty` | Seedowanie gdy tabela pusta | `seed_items` wywołane z listą | Pass |
| T-128 | Jednostkowy | `test_build_fetchers_no_keys_returns_empty` | Brak kluczy API | Pusta lista fetcherów | Pass |
| T-129 | Jednostkowy | `test_build_fetchers_only_steam_key` | Tylko klucz Steam | Jeden `SteamFetcher` | Pass |
| T-130 | Jednostkowy | `test_build_fetchers_all_keys` | Wszystkie klucze API | Trzy różne fetchery | Pass |
| T-131 | Jednostkowy | `test_build_fetchers_skinport_without_secret_skipped` | Brak `client_secret` Skinport | Skinport pomijany | Pass |
| T-132 | Jednostkowy | `test_run_poll_cycle_merges_results` | Scalanie wyników fetcherów | Lista ze wszystkich rynków | Pass |
| T-133 | Jednostkowy | `test_run_poll_cycle_handles_fetcher_exception` | Wyjątek w jednym fetcherze | Wyniki z pozostałych | Pass |
| T-134 | Jednostkowy | `test_run_poll_cycle_empty_fetchers` | Pusta lista fetcherów | Pusta lista wyników | Pass |
| T-135 | Jednostkowy | `test_resolve_direct_steam_id64` | Bezpośrednie SteamID64 | Zwraca ID64 | Pass |
| T-136 | Jednostkowy | `test_resolve_another_valid_id64` | Inne poprawne ID64 | Zwraca ID64 | Pass |
| T-137 | Jednostkowy | `test_resolve_profiles_url` | URL `/profiles/ID64` | Wyciąga ID64 | Pass |
| T-138 | Jednostkowy | `test_resolve_profiles_url_with_trailing_slash` | URL z trailing slash | Wyciąga ID64 | Pass |
| T-139 | Jednostkowy | `test_resolve_id64_embedded_in_text` | ID64 w środku tekstu | Wyciąga ID64 | Pass |
| T-140 | Jednostkowy | `test_resolve_empty_string` | Pusty string | `None` | Pass |
| T-141 | Jednostkowy | `test_resolve_none_input` | `None` na wejściu | `None` | Pass |
| T-142 | Jednostkowy | `test_resolve_no_match_random_text` | Losowy tekst bez ID | `None` | Pass |
| T-143 | Jednostkowy | `test_resolve_no_match_partial_id` | Niekompletne ID (za krótkie) | `None` | Pass |
| T-144 | Jednostkowy | `test_resolve_vanity_url_no_match` | Vanity URL bez ID64 | `None` | Pass |
| T-145 | Jednostkowy | `test_resolve_strips_leading_trailing_slashes` | ID z ukośnikami | Wyciąga ID64 | Pass |
| T-146 | Jednostkowy | `test_resolve_parametrized[76561198000000001-…]` | Parametryzowany: poprawne ID | Zwraca ID64 | Pass |
| T-147 | Jednostkowy | `test_resolve_parametrized[https://…/profiles/…]` | Parametryzowany: URL profilu | Wyciąga ID64 | Pass |
| T-148 | Jednostkowy | `test_resolve_parametrized[-None]` | Parametryzowany: pusty string | `None` | Pass |
| T-149 | Jednostkowy | `test_resolve_parametrized[None-None]` | Parametryzowany: `None` | `None` | Pass |
| T-150 | Jednostkowy | `test_resolve_parametrized[random-None]` | Parametryzowany: losowy tekst | `None` | Pass |

\* T-029 jest pomijany lokalnie (brak `DATABASE_URL`); wykonywany automatycznie w CI z kontenerem PostgreSQL.

