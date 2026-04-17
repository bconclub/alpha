-- GPFC: Ensure options_state exposes momentum_60s_pct for dashboard/entry mode panel.
-- Safe to run multiple times.

ALTER TABLE options_state
ADD COLUMN IF NOT EXISTS momentum_60s_pct NUMERIC;

COMMENT ON COLUMN options_state.momentum_60s_pct IS
'Underlying 60s momentum percent written by options_scalp for MOMENTUM_BURST visualization.';
