-- =============================================================================
-- CS2-Market-Analyzer — schemat bazy danych
-- Wykonywany automatycznie przy pierwszym uruchomieniu kontenera PostgreSQL
-- =============================================================================

-- -----------------------------------------------------------------------------
-- TABELA: items
-- Słownik przedmiotów CS2, które są śledzone.
-- Zarządzane przez: Discord bot (!add_item / !remove_item) lub seed z pliku.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items (
    id               SERIAL PRIMARY KEY,

    -- market_hash_name = unikalny identyfikator Steam używany przez wszystkie rynki
    market_hash_name TEXT        NOT NULL UNIQUE,

    -- Soft-delete: FALSE = nie pobieraj cen, ale zachowaj historię
    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,

    -- Discord user ID osoby, która dodała item (NULL = seed z pliku)
    added_by         TEXT,

    -- Opcjonalne metadane (rarity, wear, item_type, itp.) — JSONB dla elastyczności
    extra_meta       JSONB,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------------------
-- TABELA: prices
-- Historia cen — rdzeń projektu. Każdy wiersz = jeden odczyt z jednego rynku.
-- Waluta: zawsze USD. Pobierane cyklicznie przez serwis ingestion.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prices (
    id            BIGSERIAL PRIMARY KEY,

    item_id       INTEGER     NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    -- Obsługiwane rynki: 'steam' | 'skinport' | 'csfloat'
    market        TEXT        NOT NULL CHECK (market IN ('steam', 'skinport', 'csfloat')),

    -- Najniższa dostępna cena w USD
    lowest_price  NUMERIC(12, 5) NOT NULL,

    -- Liczba dostępnych ofert / wolumen (może być NULL jeśli API nie zwraca)
    quantity      INTEGER,

    -- Surowa odpowiedź API — ułatwia debugowanie i ponowny parsing
    raw_data      JSONB,

    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prices_item_market  ON prices(item_id, market);
CREATE INDEX IF NOT EXISTS idx_prices_fetched_at   ON prices(fetched_at DESC);


-- -----------------------------------------------------------------------------
-- TABELA: alerts
-- Wyniki silnika analitycznego (serwis analysis) gotowe do wysłania przez bota.
-- Wzorzec: Producent (analysis) → Konsument (discord_bot).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
    id          BIGSERIAL PRIMARY KEY,

    item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    -- 'arbitrage' | 'pump_dump' | 'price_drop'
    alert_type  TEXT    NOT NULL CHECK (alert_type IN ('arbitrage', 'pump_dump', 'price_drop')),

    -- Szczegóły alertu, np.:
    -- { "market_buy": "skinport", "price_buy": 10.50,
    --   "market_sell": "steam",   "price_sell": 13.20,
    --   "spread_pct": 25.7 }
    details     JSONB,

    sent        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indeks częściowy — discord_bot odpytuje tylko niesłane alerty
CREATE INDEX IF NOT EXISTS idx_alerts_unsent ON alerts(created_at ASC) WHERE sent = FALSE;
