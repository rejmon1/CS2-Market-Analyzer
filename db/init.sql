-- =============================================================================
-- CS2-Market-Analyzer — szkielet / przewodnik po schemacie bazy danych
-- Wykonywany automatycznie przy pierwszym uruchomieniu kontenera PostgreSQL
-- =============================================================================
--
-- WAŻNE: Ten plik to PUNKT WYJŚCIA i zestaw wskazówek, a nie gotowy schemat.
-- Zanim zacommitujesz finalne CREATE TABLE, odpowiedz sobie na pytania
-- zawarte w komentarzach poniżej. Pola oznaczone "TODO" wymagają decyzji
-- całego zespołu.
--
-- JAK PODEJŚĆ DO PROJEKTOWANIA SCHEMATU?
-- 1. Zacznij od pytania: "Co chcę CZYTAĆ?" (nie "co chcę zapisywać").
--    Np. "Chcę porównać cenę AK-47 | Redline ze Steam vs Skinport z ostatnich
--    24h" → to mówi Ci, jakie kolumny i indeksy są potrzebne.
-- 2. Używaj JSONB do przechowywania RAW odpowiedzi API póki nie wiesz,
--    których pól API będziesz regularnie potrzebować — łatwiej zapytać
--    JSONB niż dodawać ALTER TABLE za każdym razem.
-- 3. Znormalizuj dopiero gdy JSONB staje się powolny lub gdy masz pewność
--    co do struktury danych.
--
-- TRWAŁOŚĆ DANYCH (persistence):
--    Wolumen Docker (`db_data`) w docker-compose.yml trzyma dane po restarcie
--    kontenera. Pamiętaj o regularnych pg_dump jeśli zależy Ci na backupach.
--    Rozważ retencję — ile historii cen naprawdę potrzebujesz? 7 dni? 30 dni?
--    Tabela rośnie szybko przy cyklicznym pollingu co N minut.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- TABELA: items
-- Słownik przedmiotów CS2, które śledzisz.
-- -----------------------------------------------------------------------------
-- Pytania do rozstrzygnięcia przez zespół:
--   TODO: Skąd pobierasz listę śledzonych itemów? Z pliku konfiguracyjnego?
--         Ręcznie? Automatycznie z API?
--   TODO: Jakie metadane itemu są Ci potrzebne?
--         Np. skin_type (Rifle/Knife/Gloves), rarity, wear (FT/MW/FN...),
--         czy item ma StatTrak?, zewnętrzny id z Steam (market_hash_name)?
--   TODO: Czy jeden wiersz = jedna kombinacja (nazwa + wear + StatTrak)?
--         Bo "AK-47 | Redline FT" i "AK-47 | Redline MW" to osobne ceny.
--
-- PRZYKŁAD MINIMALNY (wypełnij TODO zanim uruchomisz na produkcji):
CREATE TABLE IF NOT EXISTS items (
    id                  SERIAL PRIMARY KEY,

    -- market_hash_name to unikalny identyfikator Steam — warto go trzymać
    -- jako klucz łączący dane z różnych rynków (każdy używa tej nazwy).
    market_hash_name    TEXT NOT NULL UNIQUE,

    -- TODO: zdecyduj, jakie dodatkowe kolumny są potrzebne od razu,
    --       a co możesz wyciągać na żądanie z raw_data w tabeli prices.
    -- Przykłady kandydatów:
    --   item_type    TEXT,         -- 'Rifle', 'Knife', 'Gloves', ...
    --   rarity       TEXT,         -- 'Covert', 'Classified', ...
    --   wear         TEXT,         -- 'Factory New', 'Minimal Wear', ...
    --   is_stattrak  BOOLEAN,
    --   extra_meta   JSONB,        -- wszystko inne póki nie wiesz co potrzebne

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------------------
-- TABELA: prices
-- Historia cen — rdzeń projektu. Tutaj pojawi się największy wolumen danych.
-- -----------------------------------------------------------------------------
-- Pytania do rozstrzygnięcia:
--   TODO: Jak często pollujesz API? Co 5 min? Co 1h?
--         Przy 1000 itemach × 2 rynki × co 5 min = 576 000 wierszy/dobę.
--         Przemyśl retencję (np. DELETE starsze niż 30 dni, albo osobna
--         tabela `prices_archive`).
--   TODO: Czy cena z API to cena minimalna (lowest listing), średnia (mean),
--         czy coś innego? Ważne dla algorytmu arbitrażu.
--   TODO: Jak chcesz przechowywać walutę?
--         NUMERIC(12,5) + kolumna `currency TEXT` albo zawsze USD?
--
-- PRZYKŁAD MINIMALNY:
CREATE TABLE IF NOT EXISTS prices (
    id          BIGSERIAL PRIMARY KEY,   -- BIGSERIAL bo wierszy będzie dużo

    item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    market      TEXT    NOT NULL,        -- np. 'steam', 'skinport', 'buff163'

    -- TODO: dostosuj typ i precyzję do danych z API
    price       NUMERIC(12, 5),          -- cena w walucie poniżej
    currency    TEXT NOT NULL DEFAULT 'USD',

    -- Raw odpowiedź API — bezcenne podczas debugowania i zmiany parsera
    raw_data    JSONB,

    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indeksy — dodawaj tylko te, których faktycznie używasz w zapytaniach
CREATE INDEX IF NOT EXISTS idx_prices_item_market   ON prices(item_id, market);
CREATE INDEX IF NOT EXISTS idx_prices_fetched_at    ON prices(fetched_at DESC);
-- TODO: rozważ indeks częściowy lub partycjonowanie tabeli po fetched_at
--       jeśli zamierzasz przechowywać długą historię cen.


-- -----------------------------------------------------------------------------
-- TABELA: alerts
-- Wyniki silnika analitycznego gotowe do wysłania przez bota Discord.
-- Wzorzec Producent (analysis) → Konsument (discord_bot).
-- -----------------------------------------------------------------------------
-- Pytania do rozstrzygnięcia:
--   TODO: Jakie typy alertów planujesz?
--         Np. 'arbitrage' (różnica cen między rynkami),
--             'pump_dump' (anomalia wolumenu),
--             'price_drop' (spadek poniżej progu)?
--   TODO: Co kolumna `details` powinna zawierać?
--         Przynajmniej: nazwa itemu, rynek A, rynek B, cena A, cena B,
--         różnica/%, link do listingu.
--   TODO: Czy chcesz rate-limiting (nie wysyłaj tego samego alertu częściej
--         niż raz na X minut)?
--
-- PRZYKŁAD MINIMALNY:
CREATE TABLE IF NOT EXISTS alerts (
    id          BIGSERIAL PRIMARY KEY,

    item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    alert_type  TEXT    NOT NULL,        -- TODO: enum/CHECK ograniczający typy

    -- TODO: zdecyduj co tutaj trafia — rozważ przynajmniej:
    -- { "market_buy": "skinport", "price_buy": 10.50,
    --   "market_sell": "steam",  "price_sell": 13.20,
    --   "spread_pct": 25.7,      "url": "..." }
    details     JSONB,

    sent        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indeks częściowy — discord_bot odpytuje TYLKO niesłane alerty
CREATE INDEX IF NOT EXISTS idx_alerts_unsent ON alerts(created_at ASC) WHERE sent = FALSE;

-- =============================================================================
-- NASTĘPNE KROKI (usuń ten komentarz gdy schemat jest zatwierdzony):
--   1. Rozstrzygnij wszystkie TODO powyżej z zespołem.
--   2. Zdecyduj o strategii migracji (Flyway, Alembic, albo ręczne skrypty
--      w db/migrations/).
--   3. Dodaj dane testowe w db/seed.sql (opcjonalnie).
--   4. Rozważ pg_partman do automatycznego partycjonowania tabeli prices
--      gdy baza zacznie rosnąć.
-- =============================================================================
