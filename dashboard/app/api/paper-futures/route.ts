import { NextResponse } from 'next/server';
import { getServerSupabase } from '@/lib/supabase-server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

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
      .order('opened_at', { ascending: false })
      .limit(300),
    supabase
      .from('paper_options_trades')
      .select('*')
      .order('opened_at', { ascending: false })
      .limit(300),
    supabase
      .from('bot_status')
      .select('bot_state,is_running,is_paused,uptime_seconds,timestamp,created_at,inr_usd_rate')
      .order('created_at', { ascending: false })
      .limit(1),
    supabase
      .from('paper_deposits')
      .select('lab,amount,kind'),
  ]);

  if (futuresRes.error) {
    return NextResponse.json({ error: futuresRes.error.message }, { status: 500 });
  }

  // Deposit ledger → per-lab funded total + burn (refill) count.
  const deposits = depositsRes.data ?? [];
  const sumDeposits = (lab: string) =>
    deposits.filter((d) => d.lab === lab).reduce((s, d) => s + Number(d.amount ?? 0), 0);
  const burns = (lab: string) =>
    deposits.filter((d) => d.lab === lab && d.kind === 'refill').length;

  const fundedOptions = sumDeposits('options') || 1000;
  const fundedFutures = sumDeposits('futures') || 1000;

  return NextResponse.json({
    rows: futuresRes.data ?? [],
    futures: futuresRes.data ?? [],
    options: optionsRes.data ?? [],
    botStatus: statusRes.data?.[0] ?? null,
    paperAccountUsd: 1000,
    funded: { options: fundedOptions, futures: fundedFutures },
    burns: { options: burns('options'), futures: burns('futures') },
  });
}
