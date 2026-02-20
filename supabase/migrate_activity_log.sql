-- ═══════════════════════════════════════════════════════════════
-- Activity Log — high-frequency event log for dashboard Live Activity feed
-- Replaces noisy strategy_log analysis entries with actionable events
-- (options signals, risk alerts, etc.)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.activity_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type  text NOT NULL,          -- options_entry, options_skip, options_exit, risk_alert
    pair        text NOT NULL,          -- e.g. ETH/USD:USD, BTC/USD:USD
    description text NOT NULL,          -- human-readable description
    exchange    text DEFAULT 'delta',   -- delta, binance
    metadata    jsonb DEFAULT '{}',     -- extra structured data (strike, premium, etc.)
    created_at  timestamptz DEFAULT now()
);

-- Index for dashboard queries (most recent first, by event type)
CREATE INDEX IF NOT EXISTS idx_activity_log_created
    ON public.activity_log (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_log_type
    ON public.activity_log (event_type, created_at DESC);

-- Enable realtime for this table (dashboard subscribes via Supabase channels)
ALTER PUBLICATION supabase_realtime ADD TABLE public.activity_log;

-- Auto-cleanup: keep only last 7 days of activity (runs daily via pg_cron or manual)
-- DELETE FROM public.activity_log WHERE created_at < now() - interval '7 days';
