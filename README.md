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
┌─────────────┐    czyta alerty      ╔═════▼═══════╗
│ discord_bot │ ◄─────────────────── ║  (todo)     ║
│  (komendy)  │                      ╚═════════════╝
└─────────────┘
```

**Zasada:** Discord bot i serwis analysis zawsze czytają z lokalnej bazy — nigdy nie odpytują zewnętrznych API bezpośrednio. Serwis `ingestion` jest jedynym punktem kontaktu z rynkami.

## 📦 Serwisy

| Serwis | Opis |
|--------|------|
| `ingestion` | Cykliczne pobieranie cen (Steam, Skinport, CSFloat) i zapis do bazy |
| `analysis` | Silnik arbitrażowy — placeholder, gotowy do rozbudowy |
| `discord_bot` | Bot Discord — placeholder, gotowy do rozbudowy |
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

## 💬 Planowane komendy Discord bota

Poniższe komendy zostaną dodane do serwisu `discord_bot` w kolejnej iteracji:

| Komenda | Opis |
|---------|------|
| `!add_item <market_hash_name>` | Dodaje item do listy śledzonych (wstawia do tabeli `items`) |
| `!remove_item <market_hash_name>` | Deaktywuje śledzenie itemu (soft-delete) |
| `!list_items` | Wyświetla wszystkie aktywnie śledzone itemy |
| `!price <market_hash_name>` | Pokazuje ostatnie ceny z każdego rynku (z lokalnej bazy, bez nowych zapytań do API) |
| `!alerts` | Wyświetla nowe alerty arbitrażowe (niesłane) |
| `!clear_alerts` | Oznacza wszystkie alerty jako przeczytane |

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
