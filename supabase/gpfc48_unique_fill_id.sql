-- GPFC #48: prevent duplicate option trade inserts at the DB level.
--
-- The signal path and the on_fill callback can race and both insert a row
-- for the same Delta fill (#3082/#3083 pattern). Code-side dedupe catches
-- most of them; this unique index is the backstop so the DB refuses the
-- second insert even if the check is bypassed.
--
-- exchange_fill_id is the Delta order id (see supabase/add_exchange_fill_id.sql
-- for the column). This index is partial — rows without a fill id are
-- untouched (applies only to live option inserts going forward).
--
-- Run ONCE in the Supabase SQL editor. Idempotent.

CREATE UNIQUE INDEX IF NOT EXISTS unique_exchange_fill_idx
    ON trades (exchange, exchange_fill_id)
    WHERE exchange_fill_id IS NOT NULL;
