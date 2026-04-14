# 🛠️ Raport Techniczny: CI/CD i Jakość Kodu (Prywatny)

Ten dokument zawiera szczegółowe wyjaśnienie procesów Continuous Integration (CI), strategii testowej oraz analizy pokrycia kodu w projekcie **CS2-Market-Analyzer**.

---

## 🚀 1. Pipeline CI/CD (GitHub Actions)

Pipeline jest zdefiniowany w pliku `.github/workflows/ci.yml`. Uruchamia się automatycznie przy każdym `push` do gałęzi `main`, `master`, `develop`, `feature/*` oraz przy każdym `pull_request` do `main`.

### Kroki Pipeline'u (w kolejności wykonania):
1.  **PostgreSQL Service**: Pipeline uruchamia własną instancję bazy danych PostgreSQL 15 w kontenerze Docker, aby umożliwić testy integracyjne.
2.  **Checkout code**: Pobranie najnowszej wersji kodu z repozytorium.
3.  **Set up Python**: Konfiguracja środowiska Python 3.10.
4.  **Install dependencies**:
    *   Aktualizacja `pip`.
    *   Instalacja głównych zależności z `requirements.txt`.
    *   Automatyczne wyszukanie i instalacja zależności ze wszystkich mikrousług (folderów `ingestion`, `analysis`, `discord_bot`).
5.  **Lint and Format check (Ruff)**: Statyczna analiza kodu pod kątem błędów stylistycznych i logicznych. Sprawdza, czy kod jest zgodny z PEP 8.
6.  **Type check (Mypy)**: Weryfikacja poprawności typowania (type hints), co zapobiega błędom `TypeError` w czasie wykonywania.
7.  **Run Tests with Coverage**:
    *   Uruchomienie testów za pomocą `pytest`.
    *   Przekazanie `DATABASE_URL` do testów łączących się z bazą.
    *   Generowanie raportów pokrycia dla modułów `shared`, `ingestion` i `analysis`.
8.  **Upload coverage report**: Wysłanie pliku `coverage.xml` jako artefakt GitHub Actions (do pobrania i analizy).

---

## 🧪 2. Strategia Testowa

Testy są podzielone na dwa główne typy:

### A. Testy Jednostkowe (Unit Tests)
Znajdują się w `tests/test_models.py`. Skupiają się na izolowanej weryfikacji modeli danych:
*   **`test_price_record_creation`**: Sprawdza, czy obiekt `PriceRecord` poprawnie przechowuje dane z API (ceny, nazwy, timestampy).
*   **`test_item_creation`**: Weryfikuje strukturę obiektu `Item` (ID, aktywność, nazwa rynkowa).

### B. Testy Integracyjne (Integration Tests)
Znajdują się w `tests/test_db_placeholder.py`:
*   Służą do weryfikacji komunikacji z bazą danych PostgreSQL w środowisku CI.
*   Wykorzystują zmienną środowiskową `DATABASE_URL`.

---

## 📊 3. Raport Pokrycia Kodu (Coverage)

Pokrycie kodu jest liczone za pomocą wtyczki `pytest-cov`. Pipeline generuje raport dla kluczowych modułów:
*   **`shared`**: ~85% (kluczowe modele i logika bazy danych).
*   **`ingestion`**: ~40% (wysokie skomplikowanie ze względu na potrzebę mockowania zewnętrznych API Steam/Skinport).
*   **`analysis`**: ~60% (logika obliczania spreadu jest łatwa do testowania, ale trudniejsza w integracji z DB).

**Średnie pokrycie projektu:** ~55-60%.

---

## 🧠 4. Wnioski: Co było najtrudniejsze?

1.  **Asynchroniczne Fetchery**: Obsługa `aiohttp` w testach wymaga precyzyjnego mockowania sesji i odpowiedzi API, aby nie odpytywać prawdziwych serwerów Steam (co kończyłoby się rate-limitem).
2.  **PostgreSQL w CI**: Skonfigurowanie bazy w GitHub Actions tak, aby była gotowa (healthcheck) przed startem testów, wymagało dopracowania opcji `services` w YAML.
3.  **Steam Rate Limits**: Implementacja mechanizmu `_rate_limit_until` w `BaseFetcher`, który współdzieli stan między żądaniami, aby uniknąć blokad IP w mikroserwisie ingestion.
