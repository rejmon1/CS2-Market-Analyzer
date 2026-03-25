# db

Skrypty SQL dla bazy danych **PostgreSQL**.

---

## Zawartość

| Plik | Opis |
|---|---|
| `init.sql` | Szkielet schematu z komentarzami i pytaniami TODO — uruchamiany automatycznie przy starcie kontenera |

Przyszłe pliki (do dodania gdy schema będzie zatwierdzona):
- `db/migrations/` — kolejne wersje schematu (V2, V3…)
- `db/seed.sql` — przykładowe dane testowe

---

## Jak zaprojektować schemat? (przewodnik)

### 1. Zacznij od pytania „Co chcę CZYTAĆ?"

Zamiast myśleć „jakie tabele mam zrobić", zacznij od konkretnych zapytań, które chcesz wykonywać:

- *„Chcę porównać cenę AK-47 | Redline FT ze Steam i Skinportu z ostatniej godziny"*  
  → potrzebujesz kolumn: `item_id`, `market`, `price`, `fetched_at`
- *„Chcę znaleźć itemy, gdzie różnica cen między rynkami przekracza 15%"*  
  → potrzebujesz wydajnego JOIN-u na tej samej tabeli po `item_id`
- *„Chcę historię cen z ostatnich 30 dni do wykrywania anomalii wolumenu"*  
  → potrzebujesz strategii retencji — ile danych trzymać?

### 2. Kiedy używać JSONB, a kiedy osobnych kolumn?

| Sytuacja | Zalecenie |
|---|---|
| Pole, z którego często filtrujesz/sortujesz | Osobna kolumna + indeks |
| Pole, które rzadko odpytujesz wprost | JSONB |
| Surowa odpowiedź API (debugging, zmiana parsera) | JSONB (`raw_data`) |
| Dane, których struktury jeszcze nie znasz | JSONB (możesz normalizować później) |

**Reguła kciuka:** trzymaj surową odpowiedź API zawsze w JSONB (`raw_data`). Kiedy okaże się, że jakieś pole JSONB zapytujesz w kółko, przenieś je do osobnej kolumny (`ALTER TABLE ... ADD COLUMN ...`).

### 3. Unikalny identyfikator itemu — `market_hash_name`

Każdy rynek CS2 (Steam, Skinport, Buff163…) posługuje się nazwą Steam jako wspólnym kluczem, np.:
```
AK-47 | Redline (Field-Tested)
★ Karambit | Fade (Factory New)
```

Pole `market_hash_name` z Steam API to najlepszy kandydat na unikalny identyfikator łączący dane z różnych rynków — użyj go jako naturalnego klucza w tabeli `items`.

### 4. Trwałość danych (Persistence)

Docker Volume zdefiniowany w `docker-compose.yml`:

```yaml
volumes:
  db_data:              # dane PostgreSQL przeżywają restart kontenera
```

Dane są trwałe dopóki **nie usuniesz wolumenu** (`docker compose down -v` kasuje dane!).  
Używaj `docker compose down` (bez `-v`) do zwykłego zatrzymania.

**Backup:**
```bash
# dump całej bazy
docker exec cs2-db pg_dump -U cs2user cs2db > backup_$(date +%Y%m%d).sql

# przywracanie
docker exec -i cs2-db psql -U cs2user cs2db < backup_YYYYMMDD.sql
```

### 5. Retencja danych — ile historii przechowywać?

Tabela `prices` rośnie szybko. Przykładowy rachunek:

```
1000 itemów × 2 rynki × co 5 min = ~576 000 wierszy/dobę ≈ 17M/miesiąc
```

Opcje do rozważenia:
- **Proste DELETE** — cron job kasujący wiersze starsze niż N dni
- **Partycjonowanie** (`PARTITION BY RANGE (fetched_at)`) — każdy miesiąc w osobnej partycji, stare partycje DROP
- **Tabela archiwalna** — przenoś stare dane do `prices_archive` z mniejszą precyzją

### 6. Migracje schematu

Na początku projektu ręczne skrypty w `db/migrations/` wystarczą:

```
db/migrations/
├── V1__initial_schema.sql
├── V2__add_item_rarity.sql
└── V3__add_price_index.sql
```

Gdy projekt urośnie — rozważ [Flyway](https://flywaydb.org/) lub [Alembic](https://alembic.sqlalchemy.org/).

---

## Jak uruchomić lokalnie (czysty start)?

```bash
# pierwsze uruchomienie — init.sql zostanie wykonany automatycznie
docker compose up -d db

# sprawdź logi
docker compose logs db

# połącz się z bazą
docker exec -it cs2-db psql -U cs2user -d cs2db
```

