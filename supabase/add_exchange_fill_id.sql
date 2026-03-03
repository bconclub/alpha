-- Add exchange_fill_id column to trades table for fill reconciliation dedup.
-- Run this in Supabase SQL Editor ONCE before deploying fill sync.
--
-- exchange_fill_id stores the exchange's unique fill/trade ID so the
-- reconciler can detect fills it has already processed (prevents dupes
-- across bot restarts).

ALTER TABLE trades ADD COLUMN IF NOT EXISTS exchange_fill_id TEXT;

CREATE INDEX IF NOT EXISTS idx_trades_exchange_fill_id
    ON trades(exchange_fill_id)
    WHERE exchange_fill_id IS NOT NULL;

-- Optional: backfill from existing data if you have fill IDs stored elsewhere
-- (not needed for fresh deploys — the reconciler fills this going forward)
