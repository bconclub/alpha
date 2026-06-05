-- GPFC #97: Paper futures ledger.
-- Records both futures paper-trade twins for filled options entries and
-- independent paper-only futures strategies before enabling live futures capital.

CREATE TABLE IF NOT EXISTS public.paper_futures_trades (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    option_trade_id     BIGINT REFERENCES public.trades(id) ON DELETE SET NULL,
    option_symbol       TEXT,

    pair                TEXT NOT NULL,
    base_asset          TEXT,
    setup_type          TEXT,
    direction           TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'closed', 'cancelled')),

    opened_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at           TIMESTAMPTZ,

    entry_price         NUMERIC(20,8) NOT NULL,
    current_price       NUMERIC(20,8),
    exit_price          NUMERIC(20,8),

    paper_account_usd   NUMERIC(20,8) NOT NULL DEFAULT 100,
    margin_usd          NUMERIC(20,8) NOT NULL,
    notional_usd        NUMERIC(20,8) NOT NULL,
    leverage            NUMERIC(8,2) NOT NULL DEFAULT 5,

    pnl_pct             NUMERIC(12,4) NOT NULL DEFAULT 0,
    peak_pnl_pct        NUMERIC(12,4) NOT NULL DEFAULT 0,
    gross_pnl_usd       NUMERIC(20,8) NOT NULL DEFAULT 0,
    fees_usd            NUMERIC(20,8) NOT NULL DEFAULT 0,
    pnl_usd             NUMERIC(20,8) NOT NULL DEFAULT 0,

    exit_reason         TEXT,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_paper_futures_opened_at
    ON public.paper_futures_trades(opened_at DESC);

CREATE INDEX IF NOT EXISTS idx_paper_futures_status
    ON public.paper_futures_trades(status);

CREATE INDEX IF NOT EXISTS idx_paper_futures_option_trade
    ON public.paper_futures_trades(option_trade_id)
    WHERE option_trade_id IS NOT NULL;

ALTER TABLE public.paper_futures_trades ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "Allow read access for authenticated users"
        ON public.paper_futures_trades FOR SELECT TO authenticated USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
