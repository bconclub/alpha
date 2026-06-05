-- Paper OPTIONS trades — buy-only, price-action, ride-the-wave paper lab.
-- Parallel to paper_futures_trades so the dashboard can show, per row,
-- whether it is an OPTION or a FUTURE. No real orders are ever placed.
-- BTC + ETH only. $100 paper account.

CREATE TABLE IF NOT EXISTS public.paper_options_trades (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- instrument identity
    pair            TEXT NOT NULL,                 -- e.g. BTC/USD:USD or ETH/USD:USD (underlying)
    base_asset      TEXT,                          -- BTC | ETH
    option_symbol   TEXT NOT NULL,                 -- full Delta option symbol traded on paper
    option_type     TEXT CHECK (option_type IN ('call','put')),
    strike          NUMERIC(20,8),
    expiry          TEXT,                          -- contract expiry tag (YYMMDD)
    moneyness       TEXT,                          -- ATM | OTM1 | OTM2 ... (how far from spot)

    -- strategy + lifecycle
    setup_type      TEXT,                          -- price-action lane name
    direction       TEXT CHECK (direction IN ('long','short')),  -- option directional view (call=long, put=short)
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','cancelled')),
    opened_at       TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,

    -- pricing (premium-based)
    entry_premium   NUMERIC(20,8) NOT NULL,        -- option ask paid (paper)
    current_premium NUMERIC(20,8),
    exit_premium    NUMERIC(20,8),
    spot_at_entry   NUMERIC(20,8),
    contracts       NUMERIC(20,8),
    option_multiplier NUMERIC(20,8),               -- 0.001 BTC, 0.01 ETH

    -- sizing ($100 paper account, buy-only so risk = stake)
    paper_account_usd NUMERIC(20,8) DEFAULT 100,
    stake_usd       NUMERIC(20,8) NOT NULL,        -- premium paid = max loss
    notional_usd    NUMERIC(20,8),                 -- contracts * spot * multiplier (delta-1 notional)

    -- results
    pnl_pct         NUMERIC(20,8),                 -- premium % move
    peak_pnl_pct    NUMERIC(20,8),
    gross_pnl_usd   NUMERIC(20,8),
    fees_usd        NUMERIC(20,8),
    pnl_usd         NUMERIC(20,8) DEFAULT 0,       -- net
    exit_reason     TEXT,

    metadata        JSONB DEFAULT '{}'::jsonb       -- confidence, greeks, edge, entry/exit price-action context
);

CREATE INDEX IF NOT EXISTS idx_paper_options_opened_at ON public.paper_options_trades (opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_options_status    ON public.paper_options_trades (status);
CREATE INDEX IF NOT EXISTS idx_paper_options_setup     ON public.paper_options_trades (setup_type);

ALTER TABLE public.paper_options_trades ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "paper_options_trades_select" ON public.paper_options_trades;
CREATE POLICY "paper_options_trades_select"
    ON public.paper_options_trades FOR SELECT
    TO authenticated
    USING (true);
