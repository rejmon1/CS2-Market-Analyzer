# 🏗️ POTĘŻNA I KOMPLEKSOWA DOKUMENTACJA CI/CD, JAKOŚCI I STRATEGII TESTOWEJ
**Projekt:** CS2-Market-Analyzer
**Przeznaczenie:** Dokumentacja wewnętrzna, głęboka analiza techniczna systemu kontroli jakości.

---

## 1. OPIS PIPELINE'U CI/CD (GitHub Actions)
System Continuous Integration w projekcie został zaprojektowany z myślą o architekturze mikroserwisowej. Cały proces jest zdefiniowany w pliku `.github/workflows/ci.yml` i działa jako zautomatyzowany strażnik jakości (Gatekeeper) przed wdrożeniem kodu.

### ⚙️ Wyzwalacze (Triggers)
Pipeline uruchamia się w dwóch przypadkach:
*   `push` na gałęzie `main`, `master`, `develop` oraz wszelkie gałęzie typu `feature/*`.
*   `pull_request` wycelowany w gałąź `main`.

### 🔄 Architektura i Konfiguracja Środowiska (Job: build-and-test)
Cały proces uruchamiany jest na najnowszym środowisku Ubuntu (`ubuntu-latest`). Kluczowym elementem konfiguracji jest sekcja `services`.

**Baza Danych w CI (Service Container):**
Aby umożliwić testy integracyjne, pipeline *przed* uruchomieniem kodu aplikacji podnosi pełnoprawny kontener z bazą PostgreSQL 15.
*   **Env vars:** Ustawiane są zmienne `POSTGRES_DB: cs2_test` oraz `POSTGRES_PASSWORD: password`.
*   **Healthcheck:** Pipeline nie przejdzie do testów, dopóki baza nie będzie w 100% gotowa na przyjmowanie połączeń. Realizowane jest to poprzez komendę `--health-cmd pg_isready`, powtarzaną co 10 sekund (`health-interval`), maksymalnie 5 razy (`health-retries`).

### 🛠️ Kolejność Kroków (Steps)
1.  **Checkout code (`actions/checkout@v4`)**: Pobranie najnowszej rewizji kodu z repozytorium.
2.  **Set up Python (`actions/setup-python@v5`)**: Instalacja czystego środowiska Python w wersji 3.10 (zgodnej z `pyproject.toml`).
3.  **Install dependencies**:
    *   Aktualizacja narzędzia `pip`.
    *   Instalacja głównych zależności developerskich (narzędzia do testów i lintowania).
    *   **Zaawansowany skrypt wyszukujący:** Ponieważ projekt to monorepo z mikroserwisami (`ingestion`, `analysis`, `discord_bot`, `inventory`), pipeline używa komendy uniksowej `find . -maxdepth 2 -name "requirements.txt" -not -path "./requirements.txt" -exec pip install -r {} \;`. Dzięki temu dynamicznie instaluje zależności każdego mikroserwisu z osobna, co gwarantuje kompletność środowiska.
4.  **Lint and Format check (Ruff)**:
    *   Wykonywane są komendy `ruff check .` (wykrywanie błędów logicznych i stylistycznych) oraz `ruff format --check .` (weryfikacja spójności formatowania).
5.  **Type check (Mypy)**:
    *   Statyczna analiza typów komendą `mypy .`. Weryfikuje zgodność adnotacji typów w całym kodzie, chroniąc przed błędami typu `AttributeError` w czasie działania.
6.  **Run Tests with Coverage**:
    *   Główne wywołanie testów: `pytest --cov=shared --cov=ingestion --cov=analysis --cov-report=xml --cov-report=term`.
    *   Do środowiska testowego wstrzykiwana jest zmienna `DATABASE_URL`, łącząca Pythona z wcześniej podniesionym kontenerem PostgreSQL.
7.  **Upload coverage report**: Zapisanie wygenerowanego pliku `coverage.xml` jako artefaktu w GitHub Actions, co pozwala na późniejszą wizualizację i audyt (np. w SonarQube lub Codecov).

**Zrzut ekranu / Zielony status:** Pomyślne przejście pipeline'u oznacza, że kod jest wolny od błędów składniowych, w pełni otypowany, formater nie zgłasza zastrzeżeń, a wszystkie testy asercyjne w `pytest` zwróciły status `PASSED`.

---

## 2. POZIOMY TESTÓW I RYGORYSTYCZNE UZASADNIENIE

Strategia testowa projektu została dopasowana do specyfiki rozproszonego systemu przetwarzania danych (ETL + Arbitraż).

### 🧪 A. Testy Jednostkowe (Unit Tests)
**Testowane komponenty:** Główne struktury danych i modele (np. moduł `shared/models.py`).
**Dokładna rozpiska:**
*   Plik `tests/test_models.py` izoluje testowanie klas takich jak `PriceRecord` oraz `Item`.
*   Sprawdzane jest poprawne mapowanie typów (np. konwersja float dla cen, przypisywanie timestampów z `datetime.now(timezone.utc)`).
*   **Uzasadnienie:** Mikroserwisy w tym projekcie komunikują się za pośrednictwem bazy danych. `shared/models.py` to wspólny język (kontrakt) całego systemu. Błąd w modelu spowodowałby, że `ingestion` zapisałby błędne dane, przez co `analysis` wygenerowałby fałszywe alerty arbitrażowe. Testowanie jednostkowe fundamentów to najtańsza i najszybsza polisa ubezpieczeniowa.

### 🔗 B. Testy Integracyjne (Integration Tests)
**Testowane komponenty:** Interakcja między kodem Pythona a bazą danych PostgreSQL.
**Dokładna rozpiska:**
*   Plik `tests/test_db_placeholder.py`. 
*   Wykorzystuje dekorator `@pytest.mark.skipif(os.environ.get("DATABASE_URL") is None)`. Oznacza to, że test ten inteligentnie pomija się podczas szybkiego dewelopmentu lokalnego (jeśli deweloper nie podniósł bazy), ale *wymusza* wykonanie w środowisku CI.
*   **Jakie interakcje wymagają weryfikacji?**
    *   Weryfikacja czy skrypt `db/init.sql` poprawnie tworzy tabele, indeksy (np. `idx_prices_item_market`) oraz constrainty.
    *   **Mikroserwis ↔ Baza Danych:** System działa we wzorcu Producent-Konsument. `Ingestion` wrzuca ceny (INSERT), a `Analysis` je czyta (SELECT). Integracja gwarantuje, że typy numeryczne (np. `NUMERIC(12, 5)` dla cen) w Postgresie zgadzają się z typem `float` w Pythonie.

### 🏁 C. Testy End-to-End (E2E)
**Testowane komponenty:** Cały łańcuch od zewnętrznego API aż po wysłanie wiadomości na Discord.
**Kluczowe scenariusze:**
1.  Harmonogram wyzwala pobieranie.
2.  `Ingestion` uderza do Steam/Skinport, parsuje JSON i zapisuje do DB.
3.  `Analysis` zauważa nowy wpis, porównuje z bazą rynków i liczy opłacalność (Spread).
4.  Wstawienie do bazy statusu alertu -> `Discord_bot` odczytuje i wysyła asynchronicznie wiadomość.
**Dlaczego E2E są trudne i obecnie realizowane "manualnie" (via Docker logs)?**
*   **Rate Limity i Bazy Zewnętrzne:** API Steam i Skinport posiadają bardzo ostre limity zapytań (często wymagają IP whitelisting lub nakładają tymczasowe bany za zbyt duży ruch). Zautomatyzowane uderzanie w prawdziwe API przy każdym commicie w CI zabiłoby konta.
*   **Wymagany Mocking:** Pełne E2E wymagałoby stworzenia lokalnego serwera HTTP udającego Steam i Skinport, który zwracałby spreparowane, opłacalne różnice cenowe, aby wyzwolić alert w `analysis`.

---

## 3. ANALIZA STATYCZNA VS DYNAMICZNA

Projekt polega w ogromnej mierze na zapobieganiu błędom bez uruchamiania kodu (Shift-Left Testing).

### 🛡️ Statyczna Analiza Kodu (Przed uruchomieniem)
Odpowiada za nią konfiguracja w `pyproject.toml`.
1.  **Ruff (Linter i Formatter):**
    *   *Konfiguracja:* Ograniczenie linii do 100 znaków (`line-length = 100`), celowanie w Pythona 3.10.
    *   *Zasady:* `select = ["E", "F", "B", "I"]`. E (błędy pycodestyle), F (błędy logiczne pyflakes np. niezdefiniowane zmienne), B (flake8-bugbear - pułapki w Pythonie), I (isort - sortowanie importów).
    *   To narzędzie analizuje drzewo AST kodu i wyłapuje błędy logiczne w ułamku sekundy, bez podłączania bazy danych.
2.  **Mypy (Static Type Checker):**
    *   *Konfiguracja:* `check_untyped_defs = true`, `explicit_package_bases = true`.
    *   *Cel:* Upewnia się, że funkcja oczekująca `list[PriceRecord]` nie dostanie przez przypadek `dict`. Eliminuje 90% błędów w czasie runtime'u, które normalnie wymagałyby pisania setek testów jednostkowych typu `assert isinstance(...)`.

### 🏃 Dynamiczna Analiza Kodu (W trakcie uruchomienia)
1.  **Pytest:** Uruchamia kod w środowisku testowym. Weryfikuje zachowanie biznesowe (np. czy obiekt zapisuje poprawne wartości po inicjalizacji).
2.  **Coverage (Pokrycie kodu):** Działa pod spodem za pomocą `pytest-cov`. Śledzi za pomocą wstrzykiwanych liczników (hooków) w Pythonie, które dokładnie linie kodu zostały wywołane podczas wykonywania `pytest`. Generuje twarde metryki procentowe dla kluczowych modułów.

---

## 4. WYBÓR NARZĘDZI TESTOWYCH (Frameworki i Biblioteki)

Dokładny stack wybrany dla projektu i powody stojące za tą decyzją:

*   **Pytest:** Zdecydowany zwycięzca nad wbudowanym `unittest`. Dlaczego? 
    *   Posiada czytelną składnię opartą na słowie kluczowym `assert` (zamiast archaicznego `self.assertEqual`).
    *   Posiada potężny system **fixtur**, który w przyszłości pozwoli wstrzykiwać wyczyszczoną bazę danych do każdego testu integracyjnego.
*   **pytest-asyncio:** Krytyczna wtyczka. Ponieważ serwisy `ingestion` (korzystające z `aiohttp` zamiast synchronicznego `requests`) oraz `discord_bot` (`discord.py`) są całkowicie asynchroniczne, wbudowane testy w Pythonie miałyby problem z Event Loopem. Wtyczka ta (z konfiguracją `asyncio_mode = "auto"`) pozwala pisać `async def test_...()`.
*   **pytest-cov:** Zamiast odpalać osobno narzędzie `coverage`, wtyczka integruje się z `pytest`, zwracając od razu wynik w terminalu i eksportując XML dla GitHub Actions.
*   **Ruff (zamiast Flake8/Black):** Nowoczesne narzędzie napisane w Rust. Łączy funkcjonalność 4 innych narzędzi w jednym, wykonując się 10-100x szybciej w CI/CD, co oszczędza czas (i pieniądze) na GitHub Actions.

---

## 5. KONWENCJE, NAZEWNICTWO I ZARZĄDZANIE

Projekt utrzymuje bardzo czystą strukturę organizacyjną w kwestii jakości.

*   **Lokalizacja w repozytorium:** Wszystkie testy są odseparowane od logiki biznesowej i znajdują się w głównym katalogu `/tests/`. Zapobiega to wgrywaniu kodu testowego do produkcyjnych kontenerów Docker (choć w tym przypadku pominięto plik `.dockerignore` dla testów, to standardowo tak się robi). Brak zagnieżdżania testów wewnątrz `ingestion` czy `analysis` ułatwia uruchomienie całego suita z jednego miejsca.
*   **Nazewnictwo plików:** Obowiązuje ścisła konwencja `test_*.py` (np. `test_models.py`, `test_db_placeholder.py`). Pytest domyślnie skanuje katalogi szukając właśnie tego wzorca.
*   **Nazewnictwo funkcji:** Każda funkcja testowa zaczyna się od prefiksu `test_`, po którym następuje opis tego, co jest sprawdzane, w języku angielskim ze znakiem podkreślenia (np. `def test_price_record_creation():`).
*   **Uruchamianie lokalne (Instrukcja dla dewelopera):**
    Aby uruchomić testy i lintery identycznie jak robi to maszyna w chmurze (CI), deweloper w konsoli odpala:
    ```bash
    # 1. Weryfikacja stylów
    ruff check .
    ruff format --check .
    
    # 2. Weryfikacja typów
    mypy .
    
    # 3. Uruchomienie testów z pokryciem
    pytest --cov=shared --cov=ingestion --cov=analysis
    ```

### WNIOSKI: Największe Wyzwania i Bariery (Co było najtrudniejsze?)
Najbardziej wymagającym aspektem architektonicznym pod kątem jakości było zaprojektowanie **mikroserwisowego Ingestion odpornego na błędy 429 (Too Many Requests)**.
Implementacja w `ingestion/fetchers/base.py` mechanizmu `_rate_limit_until` (współdzielonego stanu opóźnienia między pętlami asynchronicznymi) jest niezwykle trudna do przetestowania jednostkowo. Wymaga kontrolowania wirtualnego czasu (tzw. `freezegun` lub `asyncio.sleep` mockowania) oraz tworzenia fałszywego serwera `aiohttp`, aby zasymulować zwracanie nagłówka `Retry-After: 60`. Z tego powodu na tym etapie projektowym przyjęto pragmatyczne podejście polegające na poleganiu na potężnej statycznej analizie typów (Mypy) i testowaniu w środowisku Dockerowym, zamiast budowania gigantycznego moka na potrzeby samego Pytestu.
