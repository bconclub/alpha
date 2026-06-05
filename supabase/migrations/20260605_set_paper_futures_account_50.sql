-- GPFC #99: Align paper futures ledger default with the $50 futures test account.

ALTER TABLE public.paper_futures_trades
    ALTER COLUMN paper_account_usd SET DEFAULT 50;
