# 🎯 CS2 Market Analyzer

System do monitorowania i arbitrażu cen skórek CS2 oparty na mikroserwisach.

## 🏗️ Architektura

```
┌─────────────┐    ceny co N min    ┌──────────────┐
│  ingestion  │ ──────────────────► │  PostgreSQL  │
│  (fetcher)  │   Steam/Skinport/   │     (db)     │
└─────────────┘     CSFloat         └──────┬───────┘
                                           │
┌─────────────┐    czyta ceny        ┌─────▼───────┐
│  analysis   │ ◄──────────────────► │  alerty     │
│  (arbitraż) │    wstawia alerty    │  (tabela)   │
└─────────────┘                      └─────┬───────┘
                                           │
┌─────────────┐    czyta alerty      ┌─────▼───────┐
│ discord_bot │ ◄─────────────────── │  alerty     │
│  (komendy)  │    auto + na żądanie │  (tabela)   │
└─────────────┘                      └─────────────┘
```

**Zasada:** Discord bot i serwis analysis zawsze czytają z lokalnej bazy — nigdy nie odpytują zewnętrznych API bezpośrednio. Serwis `ingestion` jest jedynym punktem kontaktu z rynkami.

## 📦 Serwisy

| Serwis | Opis |
|--------|------|
| `ingestion` | Cykliczne pobieranie cen (Steam, Skinport, CSFloat) i zapis do bazy |
| `analysis` | Silnik arbitrażowy — placeholder, gotowy do rozbudowy |
| `discord_bot` | Bot Discord — komendy `!price`, `!alerts`, `!add_item`, itp. + automatyczne powiadomienia |
| `db` | PostgreSQL 16 z automatycznym inicjowaniem schematu |

## 🚀 Uruchomienie lokalne

### Wymagania

- [Docker](https://docs.docker.com/get-docker/) ≥ 24
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.20

### Krok po kroku

**1. Sklonuj repozytorium**

```bash
git clone https://github.com/rejmon1/CS2-Market-Analyzer.git
cd CS2-Market-Analyzer
```

**2. Skonfiguruj zmienne środowiskowe**

```bash
cp .env.example .env
```

Otwórz `.env` i uzupełnij klucze API (Steam działa bez klucza; Skinport i CSFloat wymagają kont):

```env
# Skinport — utwórz aplikację na https://skinport.com/account/api
SKINPORT_CLIENT_ID=twoj_client_id
SKINPORT_CLIENT_SECRET=twoj_client_secret

# CSFloat — klucz z https://csfloat.com/profile
CSFLOAT_API_KEY=twoj_klucz_api

# Jak często pobierać ceny (sekundy); 300 = co 5 minut
POLL_INTERVAL_SECONDS=300
```

> **Minimalne demo bez kluczy:** zostaw `SKINPORT_CLIENT_ID`, `SKINPORT_CLIENT_SECRET` i `CSFLOAT_API_KEY` puste — `ingestion` uruchomi się tylko z fetcherem Steam.

**3. Uruchom wszystkie kontenery**

```bash
docker compose up -d --build
```

Przy pierwszym uruchomieniu Docker zbuduje obrazy i PostgreSQL wykona `db/init.sql`. Baza jest gotowa gdy kontener `cs2-db` przejdzie health check.

**4. Sprawdź logi serwisu ingestion**

```bash
docker compose logs -f ingestion
```

Przy pierwszym starcie zobaczysz:

```
Seeded 50 default items into items table
Poll cycle: 50 items × 1 markets
[steam] Fetched 48/50 items
Poll cycle done: 48 price records inserted in 63.2s — sleeping 300s
```

**5. Sprawdź dane w bazie**

```bash
# Wejdź do kontenera PostgreSQL
docker compose exec db psql -U cs2user -d cs2db
```

```sql
-- Ile masz itemów i czy są aktywne
SELECT market_hash_name, is_active, created_at FROM items ORDER BY id;

-- Ostatnie zebrane ceny (najnowsze najpierw)
SELECT i.market_hash_name, p.market, p.lowest_price, p.quantity, p.fetched_at
FROM prices p
JOIN items i ON i.id = p.item_id
ORDER BY p.fetched_at DESC
LIMIT 30;

-- Ile rekordów zebrałeś z każdego rynku
SELECT market, COUNT(*) AS records FROM prices GROUP BY market;

-- Ostatnia cena per item per rynek (bez duplikatów)
SELECT DISTINCT ON (i.market_hash_name, p.market)
    i.market_hash_name, p.market, p.lowest_price, p.fetched_at
FROM prices p
JOIN items i ON i.id = p.item_id
ORDER BY i.market_hash_name, p.market, p.fetched_at DESC;

-- Wyjście z psql
\q
```

> **Uwaga o czasie cyklu Steam:** Steam wymaga 1,2 s przerwy między zapytaniami (publiczne API). Przy 50 itemach jeden cykl trwa ~60 s, a następnie serwis śpi `POLL_INTERVAL_SECONDS` (domyślnie 300 s). Nowy cykl startuje co ~6 minut, nie co minutę.

**6. Zatrzymaj środowisko**

```bash
docker compose down          # zatrzymuje kontenery, dane w wolumenie zachowane
docker compose down -v       # zatrzymuje i usuwa wolumen (czysta baza)
```

---

## 🧪 Jak testować aplikację (przewodnik dla dewelopera)

Ta sekcja opisuje krok po kroku, jak uruchomić i zweryfikować działanie każdego serwisu lokalnie.

### Minimalne wymagania do pierwszego testu

- Docker Desktop (lub Docker Engine) uruchomiony w tle
- Tylko to — **żadne klucze API nie są wymagane** do podstawowego testu (Steam działa bez klucza)

---

### 1. Przygotuj plik `.env`

```bash
cp .env.example .env
```

Do szybkiego testu **wystarczy taki `.env`** (reszta pól pusta):

```env
POSTGRES_USER=cs2user
POSTGRES_PASSWORD=changeme
POSTGRES_DB=cs2db

# Skinport i CSFloat - zostaw puste, ingestion uruchomi się tylko ze Steam
SKINPORT_CLIENT_ID=
SKINPORT_CLIENT_SECRET=
CSFLOAT_API_KEY=

# Skróć interwały żeby szybciej zobaczyć efekty
POLL_INTERVAL_SECONDS=60
ANALYSIS_INTERVAL_SECONDS=10

# Obniż próg arbitrażu żeby zobaczyć alerty nawet na małych różnicach cen
ARBITRAGE_MIN_SPREAD_PCT=0.1

# Discord - zostaw puste jeśli nie testujesz bota
DISCORD_TOKEN=
DISCORD_CHANNEL_ID=
ALERT_POLL_INTERVAL_SECONDS=30
```

> **Dlaczego `POLL_INTERVAL_SECONDS=60` i `ARBITRAGE_MIN_SPREAD_PCT=0.1`?**
> Przy domyślnych ustawieniach cykl trwa ~6 minut. Skrócone wartości pozwalają zobaczyć wyniki w ciągu ~2 minut. Po teście przywróć `300` i `5.0`.

---

### 2. Zbuduj i uruchom kontenery

```bash
docker compose up -d --build
```

Sprawdź, że wszystkie 4 kontenery wystartowały:

```bash
docker compose ps
```

Oczekiwany wynik:

```
NAME                     SERVICE        STATUS          PORTS
cs2-db                   db             running (healthy)
cs2-...-ingestion-1      ingestion      running
cs2-...-analysis-1       analysis       running
cs2-...-discord_bot-1    discord_bot    running
```

> Jeśli kontener `db` nie jest `healthy`, poczekaj 10–15 s i odśwież `docker compose ps`.

---

### 3. Sprawdź logi każdego serwisu

#### Serwis `ingestion` — pobieranie cen

```bash
docker compose logs -f ingestion
```

Prawidłowy start wygląda tak:

```
Seeded 50 default items into items table
Poll cycle: 50 items × 1 markets
[steam] Fetching item 1/50: AK-47 | Redline (Field-Tested)
...
[steam] Fetched 48/50 items
Poll cycle done: 48 price records inserted in 63.2s — sleeping 60s
```

Czego szukać:
- `Seeded N default items` — baza zasilona itemami ✅
- `Fetched N/50 items` — ceny pobrane ze Steam ✅
- `price records inserted` — dane zapisane w bazie ✅
- Brak `ERROR` ani `Exception` ✅

#### Serwis `analysis` — silnik arbitrażowy

```bash
docker compose logs -f analysis
```

Prawidłowe logi:

```
Analysis service started
Konfiguracja: interwał=10s, minimalny_spread=0.1%
Znaleziono 3 potencjalnych okazji arbitrażowych (próg: 0.1%)
Alert #1: 'AK-47 | Redline (Field-Tested)' | kup na steam → sprzedaj na skinport | spread netto: 2.30%
Cykl zakończony — wygenerowano 3 alertów
```

> Jeśli widzisz `Brak cen w bazie — pomijam cykl`, to ingestion jeszcze nie zebrał danych — poczekaj aż ingestion ukończy pierwszy cykl.

> Alerty arbitrażowe wymagają cen z **co najmniej dwóch rynków**. Przy samym Steam zobaczysz `0 alertów` — to normalne. Dodaj klucze Skinport / CSFloat żeby alerty działały.

#### Serwis `discord_bot`

```bash
docker compose logs discord_bot
```

Bez ustawionego `DISCORD_TOKEN` bot zakończy pracę z komunikatem:

```
DISCORD_TOKEN is not set — bot nie zostanie uruchomiony
Ustaw DISCORD_TOKEN w pliku .env i zrestartuj kontener discord_bot.
```

Po ustawieniu tokenu prawidłowy start wygląda tak:

```
Discord bot service starting…
Bot zalogowany jako CS2Bot#1234 (id: 123456789)
Prefiks komend: !
Kanał alertów: 987654321
```

---

### 4. Zweryfikuj dane w bazie PostgreSQL

```bash
docker compose exec db psql -U cs2user -d cs2db
```

#### Sprawdź itemy

```sql
-- Ile itemów załadował seed
SELECT COUNT(*) FROM items;
-- Oczekiwane: 50

-- Kilka przykładowych nazw
SELECT market_hash_name FROM items LIMIT 5;
```

#### Sprawdź zebrane ceny

```sql
-- Ile rekordów cen zebrano z każdego rynku
SELECT market, COUNT(*) AS rekordy FROM prices GROUP BY market;

-- Ostatnie 10 zebranych cen (najnowsze pierwsze)
SELECT i.market_hash_name, p.market, p.lowest_price, p.fetched_at
FROM prices p
JOIN items i ON i.id = p.item_id
ORDER BY p.fetched_at DESC
LIMIT 10;
```

#### Sprawdź alerty arbitrażowe

```sql
-- Wszystkie alerty (najnowsze pierwsze)
SELECT a.id, i.market_hash_name, a.alert_type,
       a.details->>'market_buy'  AS kup_na,
       a.details->>'market_sell' AS sprzedaj_na,
       a.details->>'spread_pct'  AS spread,
       a.sent, a.created_at
FROM alerts a
JOIN items i ON i.id = a.item_id
ORDER BY a.created_at DESC
LIMIT 20;

-- Tylko niesłane alerty
SELECT COUNT(*) AS niesłane FROM alerts WHERE sent = FALSE;
```

#### Sprawdź prowizje rynków

```sql
-- Prowizje wgrane przy starcie (init.sql)
SELECT * FROM market_fees;
```

Wyjdź z psql:

```sql
\q
```

---

### 5. Test z kluczami Skinport i CSFloat

Aby przetestować pełną funkcjonalność arbitrażu (ceny z wielu rynków), dodaj klucze do `.env`:

```env
SKINPORT_CLIENT_ID=twoj_client_id
SKINPORT_CLIENT_SECRET=twoj_client_secret
CSFLOAT_API_KEY=twoj_klucz_api
```

Następnie zrestartuj serwis ingestion:

```bash
docker compose restart ingestion
```

Po następnym cyklu ingestion zobaczysz w logach trzy rynki:

```
Poll cycle: 50 items × 3 markets
[steam]    Fetched 48/50 items
[skinport] Fetched 50/50 items
[csfloat]  Fetched 47/50 items
```

A silnik analizy będzie miał dane do porównywania cen między rynkami.

---

### 6. Test Discord bota

Jeśli chcesz przetestować bota:

1. Wejdź na [Discord Developer Portal](https://discord.com/developers/applications)
2. Stwórz nową aplikację → Bot → skopiuj **Token**
3. W sekcji **Privileged Gateway Intents** włącz **Message Content Intent**
4. Zaproś bota na swój serwer testowy (OAuth2 → URL Generator → scope: `bot`, uprawnienia: `Send Messages`, `Read Message History`)
5. Skopiuj **ID kanału** (prawy klik na kanał → "Kopiuj ID kanału" przy włączonym trybie dewelopera w ustawieniach Discord)
6. Uzupełnij `.env`:

```env
DISCORD_TOKEN=twoj_token_bota
DISCORD_CHANNEL_ID=id_kanalu
```

7. Zrestartuj bota:

```bash
docker compose restart discord_bot
```

8. Sprawdź logi:

```bash
docker compose logs discord_bot
```

Oczekiwany wynik:

```
Discord bot service starting…
Bot zalogowany jako CS2Bot#1234 (id: 123456789)
Prefiks komend: !
Kanał alertów: 987654321
```

9. Przetestuj komendy na swoim serwerze Discord:

```
!list_items
!price AK-47 | Redline (Field-Tested)
!alerts
!add_item AWP | Asiimov (Field-Tested)
!remove_item AWP | Asiimov (Field-Tested)
!clear_alerts
```

Bot będzie też automatycznie wysyłać nowe alerty arbitrażowe na skonfigurowany kanał co 30 sekund (zmienna `ALERT_POLL_INTERVAL_SECONDS`).

---

### 7. Czyszczenie środowiska

```bash
# Zatrzymaj kontenery (dane w bazie zachowane)
docker compose down

# Zatrzymaj i usuń wszystkie dane (czysta baza przy następnym starcie)
docker compose down -v

# Przebuduj obrazy od zera (po zmianie kodu)
docker compose up -d --build
```

---

### 8. Typowe problemy

| Problem | Przyczyna | Rozwiązanie |
|---------|-----------|-------------|
| `db` nie jest `healthy` | PostgreSQL jeszcze startuje | Poczekaj 15 s, sprawdź `docker compose logs db` |
| `ingestion` ciągle restartuje | Błąd połączenia z bazą | Upewnij się, że `db` jest `healthy` przed sprawdzaniem logów |
| `Fetched 0/50 items` | Steam odrzucił zapytania (rate limit) | Poczekaj kilka minut, Steam API ma limity |
| `Znaleziono 0 okazji arbitrażowych` | Ceny tylko z jednego rynku | Dodaj klucze Skinport/CSFloat lub obniż `ARBITRAGE_MIN_SPREAD_PCT` |
| Kontener `discord_bot` zatrzymuje się | Brak tokenu lub zły token | Ustaw `DISCORD_TOKEN` w `.env`, włącz **Message Content Intent** w Developer Portal |

---

## 🔧 Zmiana listy śledzonych itemów

Edytuj `ingestion/default_items.json` przed pierwszym uruchomieniem — plik zawiera 50 popularnych skinów. Po uruchomieniu, jeśli tabela `items` jest już uzupełniona, plik jest ignorowany.

Aby dodać/usunąć item ręcznie (przez psql):

```sql
-- Dodaj nowy item
INSERT INTO items (market_hash_name) VALUES ('AK-47 | Asiimov (Battle-Scarred)');

-- Deaktywuj śledzenie (soft-delete)
UPDATE items SET is_active = FALSE WHERE market_hash_name = 'AK-47 | Asiimov (Battle-Scarred)';
```

---

## 💬 Komendy Discord bota

Wszystkie komendy używają prefiksu `!`. Bot czyta wyłącznie z lokalnej bazy — nigdy nie odpytuje zewnętrznych API.

| Komenda | Opis |
|---------|------|
| `!add_item <market_hash_name>` | Dodaje item do listy śledzonych (wstawia do tabeli `items`) |
| `!remove_item <market_hash_name>` | Deaktywuje śledzenie itemu (soft-delete, historia cen zachowana) |
| `!list_items` | Wyświetla wszystkie aktywnie śledzone itemy |
| `!price <market_hash_name>` | Pokazuje ostatnie ceny z każdego rynku (z lokalnej bazy) |
| `!alerts` | Wyświetla nowe alerty arbitrażowe (niesłane) |
| `!clear_alerts` | Oznacza wszystkie alerty jako przeczytane |

Dodatkowo bot automatycznie wysyła nowe alerty na kanał `DISCORD_CHANNEL_ID` co `ALERT_POLL_INTERVAL_SECONDS` sekund (domyślnie 30 s).

Przykłady `market_hash_name` (dokładna nazwa ze Steam Market):
- `AK-47 | Redline (Field-Tested)`
- `AWP | Asiimov (Field-Tested)`
- `Karambit | Doppler (Factory New)`
- `StatTrak™ M4A1-S | Hyper Beast (Field-Tested)`

---

## 👥 Zespół

| Rola | Osoba |
|------|-------|
| Product Owner | Hubert / @rejmon1 |
| Architekt Chmury | Dawid / @dawbie |
| Backend | Aleks / @whatanxx |
| QA | Radek / @RakosIX |
