-- Options state table: engine writes every 30s, dashboard reads in realtime
-- One row per pair (BTC/USD:USD, ETH/USD:USD) — upserted on each write

CREATE TABLE IF NOT EXISTS options_state (
    pair          TEXT PRIMARY KEY,
    spot_price    DOUBLE PRECISION,
    expiry        TIMESTAMPTZ,
    expiry_label  TEXT,              -- "Feb 21 12:00 UTC — 19h away"
    atm_strike    DOUBLE PRECISION,
    call_premium  DOUBLE PRECISION,  -- ATM call premium (fetched)
    put_premium   DOUBLE PRECISION,  -- ATM put premium (fetched)
    signal_strength INTEGER DEFAULT 0,
    signal_side   TEXT,              -- 'long' | 'short' | null
    signal_reason TEXT,
    -- Active position info (null when no position)
    position_side TEXT,              -- 'call' | 'put' | null
    position_strike DOUBLE PRECISION,
    position_symbol TEXT,
    entry_premium DOUBLE PRECISION,
    current_premium DOUBLE PRECISION,
    pnl_pct       DOUBLE PRECISION,
    pnl_usd       DOUBLE PRECISION,
    trailing_active BOOLEAN DEFAULT FALSE,
    highest_premium DOUBLE PRECISION,
    -- Timestamps
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Enable realtime
ALTER PUBLICATION supabase_realtime ADD TABLE options_state;

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_options_state_updated ON options_state (updated_at DESC);
