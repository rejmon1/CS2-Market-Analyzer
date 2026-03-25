# CS2-Market-Analyzer

System do analizy rynku CS2 w architekturze mikroserwisowej (Python + PostgreSQL + Docker).

---

## Architektura

### Diagram przepływu danych

```
┌─────────────────────────────────────────────────────────────────────┐
│                          VPS / Docker Host                          │
│                                                                     │
│  ┌──────────────┐   zapis cen (JSONB)   ┌────────────────────────┐ │
│  │  ingestion   │ ────────────────────► │                        │ │
│  │              │                       │      PostgreSQL         │ │
│  │ Steam API    │                       │                        │ │
│  │ Skinport API │   odczyt cen          │  ┌─────────────────┐  │ │
│  └──────────────┘                       │  │ items           │  │ │
│                       ┌────────────────►│  │ prices  (JSONB) │  │ │
│  ┌──────────────┐     │  zapis alertów  │  │ alerts          │  │ │
│  │   analysis   │ ────┤ ──────────────► │  └─────────────────┘  │ │
│  │              │     │                 │                        │ │
│  │ arbitraż     │     │  odczyt alertów └────────────────────────┘ │
│  │ pump & dump  │     │        ▲                                   │
│  └──────────────┘     │        │                                   │
│                        │        │                                   │
│  ┌──────────────┐      │        │                                   │
│  │ discord_bot  │ ─────┘        │                                   │
│  │              │ ──────────────┘                                   │
│  │ konsument    │  nasłuchuje nowych alertów (sent = FALSE)         │
│  └──────────────┘                                                   │
│         │                                                           │
└─────────┼───────────────────────────────────────────────────────────┘
          │  Discord API
          ▼
   ┌─────────────┐
   │  Kanał      │
   │  Discord    │
   └─────────────┘
```

### Wzorzec komunikacji: Producent–Konsument przez bazę danych

Serwisy **nie komunikują się ze sobą bezpośrednio** — jedynym medium wymiany danych jest PostgreSQL. Dzięki temu:
- awaria bota Discord nie zatrzymuje zbierania ani analizy danych,
- każdy serwis można restartować niezależnie,
- w przyszłości łatwo dodać kolejny konsument (np. Telegram Bot).

| Rola | Serwis | Działanie |
|---|---|---|
| **Producent danych** | `ingestion` | Poll API → zapis do `prices` |
| **Producent alertów** | `analysis` | Odczyt `prices` → analiza → zapis do `alerts` |
| **Konsument alertów** | `discord_bot` | Odczyt `alerts WHERE sent=FALSE` → wysłanie → aktualizacja `sent=TRUE` |

---

## Motywacje technologiczne

#### 1. Język: Python
Szybkość prototypowania (bogate biblioteki HTTP/JSON: `requests`, `aiohttp`), prosta obsługa API rynków CS2 i natywne wsparcie dla podejścia mikroserwisowego. Każdy serwis to mała, wyspecjalizowana aplikacja — bez ryzyka monolitu.

#### 2. Baza danych: PostgreSQL
- **JSONB** — natywny zapis surowych odpowiedzi API bez kosztownej transformacji danych. Możesz zacząć od `raw_data JSONB` i normalizować pola stopniowo.
- **JOIN-y** — błyskawiczne parowanie cen tego samego przedmiotu z wielu rynków (arbitraż).
- **Brak kosztów per-operację** — w przeciwieństwie do chmurowych NoSQL (Firebase itp.) własna instancja PostgreSQL nie generuje kosztów za każdy zapis/odczyt, co ma kluczowe znaczenie przy tysiącach aktualizacji cen dziennie.

#### 3. Infrastruktura: VPS + Docker
- Stały, przewidywalny koszt (< 50 $/mies., np. Hetzner/DigitalOcean).
- Każdy serwis działa w izolowanym kontenerze → **Fault Tolerance**: awaria bota Discord nie zatrzymuje zbierania danych.
- Jedno polecenie (`docker compose up`) uruchamia całe środowisko.

#### 4. Warstwa prezentacji: Discord Bot
Świadoma rezygnacja z front-endu webowego — oszczędza tygodnie pracy i daje powiadomienia push w czasie rzeczywistym.

---

## Struktura repozytorium

```
CS2-Market-Analyzer/
├── ingestion/       # Moduł pobierający dane z rynków (Steam, Skinport, …)
├── analysis/        # Silnik analityczny — wykrywanie arbitrażu, anomalii
├── discord_bot/     # Bot Discord — konsument alertów z bazy danych
├── shared/          # Kod wspólny: modele, walidacje, helpery
├── db/              # Skrypty SQL: szkielet schematu, migracje, seed
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Ogólny workflow

```
┌─ ingestion ─────────────────────────────────────────────────┐
│  co N minut:                                                 │
│    dla każdego śledzonego itemu:                             │
│      GET /api/steam/{item}  → zapis do prices (raw JSONB)   │
│      GET /api/skinport/{item} → zapis do prices (raw JSONB) │
└─────────────────────────────────────────────────────────────┘
           ↓ (dane w PostgreSQL)
┌─ analysis ──────────────────────────────────────────────────┐
│  co N minut:                                                 │
│    SELECT ceny z ostatnich X minut per item per market       │
│    oblicz spread cen między rynkami (arbitraż)               │
│    sprawdź anomalie wolumenowe (pump & dump)                 │
│    jeśli okazja > próg: INSERT do alerts (sent=FALSE)        │
└─────────────────────────────────────────────────────────────┘
           ↓ (alerty w PostgreSQL)
┌─ discord_bot ───────────────────────────────────────────────┐
│  co N sekund:                                                │
│    SELECT * FROM alerts WHERE sent=FALSE                     │
│    wyślij wiadomość na kanał Discord                         │
│    UPDATE alerts SET sent=TRUE WHERE id=...                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Szybki start

```bash
cp .env.example .env   # uzupełnij zmienne środowiskowe
docker compose up --build
```

> Szczegółowe instrukcje konfiguracji pojawią się wraz z rozwojem projektu.  
> Przeczytaj `db/README.md` przed zaprojektowaniem finalnego schematu bazy danych.

---

## Backlog zadań (podział ról)

Poniższe zadania są przeznaczone do przepisania jako **GitHub Issues** w projekcie i przypisania do konkretnych osób w teamie.

### 🔵 `ingestion` — Moduł pobierania danych
- [ ] **[INGESTION-1]** Zdefiniować listę śledzonych itemów (plik konfiguracyjny / tabela w DB)
- [ ] **[INGESTION-2]** Zaimplementować klienta Steam Community Market API (pobieranie cen)
- [ ] **[INGESTION-3]** Zaimplementować klienta Skinport API (pobieranie cen)
- [ ] **[INGESTION-4]** Cykliczny scheduler (co N minut) z zapisem do tabeli `prices`
- [ ] **[INGESTION-5]** Obsługa błędów, retry i rate-limiting (429 Too Many Requests)
- [ ] **[INGESTION-6]** Testy jednostkowe klientów API (mock HTTP)

### 🟡 `analysis` — Silnik analityczny
- [ ] **[ANALYSIS-1]** Zaprojektować algorytm wykrywania arbitrażu (JOIN cen item+market)
- [ ] **[ANALYSIS-2]** Zdefiniować progi alertów (min. % spread, min. wolumen)
- [ ] **[ANALYSIS-3]** Zaimplementować wykrywanie anomalii wolumenowych (Pump & Dump)
- [ ] **[ANALYSIS-4]** Zapis okazji jako `alerts` (sent=FALSE) do bazy
- [ ] **[ANALYSIS-5]** Zapobieganie duplikatom alertów (ten sam item w ciągu X minut)
- [ ] **[ANALYSIS-6]** Testy jednostkowe algorytmów (sample data)

### 🟣 `discord_bot` — Bot Discord
- [ ] **[BOT-1]** Skonfigurować bota Discord (token, uprawnienia, docelowy kanał)
- [ ] **[BOT-2]** Zaimplementować pętlę konsumenta (`SELECT ... WHERE sent=FALSE`)
- [ ] **[BOT-3]** Zaprojektować format wiadomości Discord (Embed z linkami do listingów)
- [ ] **[BOT-4]** Zaimplementować aktualizację `sent=TRUE` po wysłaniu
- [ ] **[BOT-5]** Obsługa błędów API Discord (retry, rate-limit)

### 🟢 `shared` — Kod wspólny
- [ ] **[SHARED-1]** Modele danych (dataclasses / Pydantic) dla Item, Price, Alert
- [ ] **[SHARED-2]** Warstwa dostępu do bazy danych (connection pool, helper queries)
- [ ] **[SHARED-3]** Konfiguracja środowiskowa (czytanie z `.env` / zmiennych środowiskowych)
- [ ] **[SHARED-4]** Logger współdzielony przez wszystkie serwisy

### 🔴 `db` — Baza danych
- [ ] **[DB-1]** Rozstrzygnąć wszystkie TODO w `db/init.sql` i zatwierdzić finalny schemat
- [ ] **[DB-2]** Zdefiniować strategię retencji danych (ile dni historii cen przechowywać)
- [ ] **[DB-3]** Skonfigurować regularne backupy (`pg_dump` jako cron/docker job)
- [ ] **[DB-4]** Dodać przykładowe dane testowe (`db/seed.sql`)
- [ ] **[DB-5]** Zdecydować o narzędziu do migracji (ręczne skrypty vs Alembic vs Flyway)

### ⚪ `infrastructure` — Infrastruktura
- [ ] **[INFRA-1]** Uzupełnić `.env.example` o wszystkie wymagane zmienne
- [ ] **[INFRA-2]** Skonfigurować środowisko deweloperskie (onboarding nowego dewelopera)
- [ ] **[INFRA-3]** Wybrać i skonfigurować VPS (Hetzner / DigitalOcean)
- [ ] **[INFRA-4]** Deployment pierwszej wersji na VPS (`docker compose up -d`)
- [ ] **[INFRA-5]** Monitorowanie kontenerów (logi, auto-restart, health checks)


