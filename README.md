# CS2-Market-Analyzer

System do analizy rynku CS2 w architekturze mikroserwisowej (Python + PostgreSQL + Docker).

---

## Architektura

### Motywacje i założenia

Projekt oparty jest na kilku kluczowych decyzjach technologicznych, które razem tworzą spójną, ekonomiczną i skalowalną infrastrukturę:

#### 1. Język: Python
Szybkość prototypowania (bogate biblioteki HTTP/JSON: `requests`, `aiohttp`), prosta obsługa API rynków CS2 i natywne wsparcie dla podejścia mikroserwisowego. Każdy serwis to mała, wyspecjalizowana aplikacja — bez ryzyka monolitu.

#### 2. Baza danych: PostgreSQL
- **JSONB** — natywny zapis surowych odpowiedzi API bez kosztownej transformacji danych.
- **JOIN-y** — błyskawiczne parowanie cen tego samego przedmiotu z wielu rynków (arbitraż).
- **Brak kosztów per-operację** — w przeciwieństwie do chmurowych NoSQL (Firebase itp.) własna instancja PostgreSQL nie generuje kosztów za każdy zapis/odczyt, co ma kluczowe znaczenie przy tysiącach aktualizacji cen dziennie.

#### 3. Infrastruktura: VPS + Docker
- Stały, przewidywalny koszt (< 50 $/mies., np. Hetzner/DigitalOcean).
- Każdy serwis działa w izolowanym kontenerze → **Fault Tolerance**: awaria bota Discord nie zatrzymuje zbierania danych.
- Jedno polecenie (`docker compose up`) uruchamia całe środowisko.

#### 4. Warstwa prezentacji: Discord Bot (wzorzec Producent–Konsument)
Świadoma rezygnacja z front-endu webowego na rzecz bota Discord, co oszczędza tygodnie pracy.
- **Producent** (silnik analityczny) — wyszukuje okazje i zapisuje „alerty" do bazy.
- **Konsument** (discord_bot) — nasłuchuje nowych alertów i wysyła powiadomienia.
- Awaria API Discord nie wpływa na ciągłość analizy. System łatwo rozbudować o kolejne kanały (Telegram itp.).

---

## Struktura repozytorium

```
CS2-Market-Analyzer/
├── ingestion/       # Moduł pobierający dane z rynków (Steam, Skinport, …)
├── analysis/        # Silnik analityczny — wykrywanie arbitrażu, anomalii
├── discord_bot/     # Bot Discord — konsument alertów z bazy danych
├── shared/          # Kod wspólny: modele, walidacje, helpery
├── db/              # Skrypty SQL: schemat, migracje, dane przykładowe
├── docker-compose.yml
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Ogólny workflow

1. **ingestion** cyklicznie pobiera ceny z API rynków i zapisuje surowe dane (JSONB) do PostgreSQL.
2. **analysis** przetwarza zebrane dane, wykrywa okazje arbitrażowe i anomalie wolumenowe (Pump & Dump), zapisuje wyniki jako „alerty" w bazie.
3. **discord_bot** nasłuchuje tabeli alertów i wysyła powiadomienia do kanału Discord.
4. Wszystkie serwisy komunikują się wyłącznie przez bazę danych PostgreSQL (luźne powiązanie).

---

## Szybki start (placeholder)

```bash
cp .env.example .env   # uzupełnij zmienne środowiskowe
docker compose up --build
```

> Szczegółowe instrukcje konfiguracji pojawią się wraz z rozwojem projektu.
