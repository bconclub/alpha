import { NextResponse } from 'next/server';
import { getServerSupabase } from '@/lib/supabase-server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// V3 era cutover (2026-06-09 21:21 UTC): both labs re-seeded to exactly $1,000.
// The dashboard shows the V3 era only — a clean $1,000 start. All V2 history
// stays untouched in the DB; the era-2 record lives in engine/PAPER_RESULTS.md.
const ERA_START = '2026-06-09T21:21:00Z';
const ERA_SEED_USD = 1000;

export async function GET() {
  const supabase = getServerSupabase();
  if (!supabase) {
    return NextResponse.json(
      { error: 'Server Supabase client is not configured.' },
      { status: 500 },
    );
  }

  const [futuresRes, optionsRes, statusRes, depositsRes] = await Promise.all([
    supabase
      .from('paper_futures_trades')
      .select('*')
      .neq('status', 'cancelled')
      .gte('opened_at', ERA_START)
      .order('opened_at', { ascending: false })
      .limit(300),
    supabase
      .from('paper_options_trades')
      .select('*')
      .neq('status', 'cancelled')
      .gte('opened_at', ERA_START)
      .order('opened_at', { ascending: false })
      .limit(300),
    supabase
      .from('bot_status')
      .select('bot_state,is_running,is_paused,uptime_seconds,timestamp,created_at,inr_usd_rate')
      .order('created_at', { ascending: false })
      .limit(1),
    supabase
      .from('paper_deposits')
      .select('lab,amount,kind,created_at')
      .gte('created_at', ERA_START),
  ]);

  if (futuresRes.error) {
    return NextResponse.json({ error: futuresRes.error.message }, { status: 500 });
  }

  // Era ledger: every lab starts the era at exactly $1,000; only deposits made
  // DURING the era (refills after a burn) add to funded.
  const deposits = depositsRes.data ?? [];
  const sumDeposits = (lab: string) =>
    deposits.filter((d) => d.lab === lab).reduce((s, d) => s + Number(d.amount ?? 0), 0);
  const burns = (lab: string) =>
    deposits.filter((d) => d.lab === lab && d.kind === 'refill').length;

  const fundedOptions = ERA_SEED_USD + sumDeposits('options');
  const fundedFutures = ERA_SEED_USD + sumDeposits('futures');

  return NextResponse.json({
    rows: futuresRes.data ?? [],
    futures: futuresRes.data ?? [],
    options: optionsRes.data ?? [],
    botStatus: statusRes.data?.[0] ?? null,
    paperAccountUsd: ERA_SEED_USD,
    era: { name: 'V3', start: ERA_START, note: 'fresh $1,000 start — V2 history in engine/PAPER_RESULTS.md' },
    funded: { options: fundedOptions, futures: fundedFutures },
    burns: { options: burns('options'), futures: burns('futures') },
  });
}
