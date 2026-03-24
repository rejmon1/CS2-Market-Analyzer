-- Schemat bazy danych CS2-Market-Analyzer
-- Wykonywany automatycznie przy pierwszym uruchomieniu kontenera PostgreSQL

-- Przedmioty CS2
CREATE TABLE IF NOT EXISTS items (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    item_type   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Historia cen z rynków
CREATE TABLE IF NOT EXISTS prices (
    id          SERIAL PRIMARY KEY,
    item_id     INTEGER REFERENCES items(id) ON DELETE CASCADE,
    market      TEXT NOT NULL,          -- np. 'steam', 'skinport'
    price_usd   NUMERIC(10, 2),
    raw_data    JSONB,                  -- surowa odpowiedź API
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prices_item_market ON prices(item_id, market);
CREATE INDEX IF NOT EXISTS idx_prices_fetched_at  ON prices(fetched_at DESC);

-- Alerty analityczne (producent: analysis, konsument: discord_bot)
CREATE TABLE IF NOT EXISTS alerts (
    id          SERIAL PRIMARY KEY,
    item_id     INTEGER REFERENCES items(id) ON DELETE CASCADE,
    alert_type  TEXT NOT NULL,          -- np. 'arbitrage', 'pump_dump'
    details     JSONB,
    sent        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_sent ON alerts(sent) WHERE sent = FALSE;
