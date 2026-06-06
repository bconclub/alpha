-- Paper deposit ledger — tracks each lab's funded bankroll and auto-refills.
-- balance(lab) = sum(amount where lab) + sum(closed pnl_usd in that lab's trades).
-- The hourly co-work routine inserts a 'refill' row (+$1000) whenever a lab burns
-- through its bankroll, so the labs run forever and we count how often each burns.
CREATE TABLE IF NOT EXISTS public.paper_deposits (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    lab         TEXT NOT NULL CHECK (lab IN ('options','futures')),
    amount      NUMERIC(20,8) NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'refill' CHECK (kind IN ('seed','refill')),
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_paper_deposits_lab ON public.paper_deposits (lab);
ALTER TABLE public.paper_deposits ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS paper_deposits_select ON public.paper_deposits;
CREATE POLICY paper_deposits_select ON public.paper_deposits FOR SELECT TO authenticated USING (true);

INSERT INTO public.paper_deposits (lab, amount, kind, note) VALUES
  ('options', 1000, 'seed', 'initial bankroll'),
  ('futures', 1000, 'seed', 'initial bankroll');
