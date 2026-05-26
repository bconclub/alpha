-- GPFC #84: Fix live monitoring schema drift.
-- Safe to run multiple times.

-- options_state receives these dashboard/debug fields from options_scalp.py.
ALTER TABLE public.options_state
ADD COLUMN IF NOT EXISTS exit_config JSONB,
ADD COLUMN IF NOT EXISTS entry_config JSONB,
ADD COLUMN IF NOT EXISTS peak_trail_pending_ticks INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS spot_momentum_20s_pct NUMERIC;

COMMENT ON COLUMN public.options_state.exit_config IS
'Live options exit threshold snapshot written by options_scalp.';
COMMENT ON COLUMN public.options_state.entry_config IS
'Live options entry threshold snapshot written by options_scalp.';
COMMENT ON COLUMN public.options_state.peak_trail_pending_ticks IS
'Number of consecutive ticks that peak-trail confirmation has been pending.';
COMMENT ON COLUMN public.options_state.spot_momentum_20s_pct IS
'Underlying 20s momentum percent used by options exit veto/telemetry.';

-- activity_log is the append-only feed for dashboard options/risk events.
CREATE TABLE IF NOT EXISTS public.activity_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,
    pair TEXT NOT NULL,
    description TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'delta',
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_activity_log_created_at
    ON public.activity_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_pair_exchange
    ON public.activity_log (pair, exchange, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_event_type
    ON public.activity_log (event_type);

ALTER TABLE public.activity_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public read activity_log" ON public.activity_log;
CREATE POLICY "Allow public read activity_log"
    ON public.activity_log
    FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Allow service role write activity_log" ON public.activity_log;
CREATE POLICY "Allow service role write activity_log"
    ON public.activity_log
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE public.activity_log IS
'Append-only dashboard activity feed for options entries, exits, skips, and risk events.';
