import { NextResponse } from 'next/server';
import { getServerSupabase } from '@/lib/supabase-server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

type Row = Record<string, unknown>;

function agg(rows: Row[], pnlKey: string) {
  const lanes: Record<
    string,
    {
      closed: number;
      open: number;
      wins: number;
      net: number;
      fees: number;
      peakSum: number;
      lastOpen: string | null;
      exits: Record<string, number>;
    }
  > = {};
  for (const r of rows) {
    const lane = String(r.setup_type ?? 'UNKNOWN');
    if (!lanes[lane])
      lanes[lane] = {
        closed: 0,
        open: 0,
        wins: 0,
        net: 0,
        fees: 0,
        peakSum: 0,
        lastOpen: null,
        exits: {},
      };
    const L = lanes[lane];
    const openedAt = r.opened_at ? String(r.opened_at) : null;
    if (openedAt && (!L.lastOpen || openedAt > L.lastOpen)) L.lastOpen = openedAt;
    if (r.status === 'closed') {
      L.closed += 1;
      const pnl = Number(r[pnlKey] ?? 0);
      L.net += pnl;
      if (pnl > 0) L.wins += 1;
      L.fees += Number(r.fees_usd ?? 0);
      L.peakSum += Number(r.peak_pnl_pct ?? 0);
      const ex = String(r.exit_reason ?? 'unknown');
      L.exits[ex] = (L.exits[ex] ?? 0) + 1;
    } else {
      L.open += 1;
    }
  }
  return Object.entries(lanes)
    .map(([lane, L]) => ({
      lane,
      closed: L.closed,
      open: L.open,
      win_pct: L.closed ? Math.round((100 * L.wins) / L.closed) : null,
      net: Math.round(L.net * 100) / 100,
      fees: Math.round(L.fees * 100) / 100,
      avg_peak_pct: L.closed ? Math.round(L.peakSum / L.closed) : null,
      last_open: L.lastOpen,
      exits: L.exits,
    }))
    .sort((a, b) => b.net - a.net);
}

/**
 * Compact per-lane paper trading summary.
 * Query params:
 *   since — ISO timestamp (default: 48h ago)
 * Built as a stable, low-token check-in source for the 2-hourly
 * knowledge-base routine (works even without direct DB access).
 */
export async function GET(request: Request) {
  const supabase = getServerSupabase();
  if (!supabase) {
    return NextResponse.json(
      { error: 'Server Supabase client is not configured.' },
      { status: 500 },
    );
  }

  const { searchParams } = new URL(request.url);
  const since =
    searchParams.get('since') ??
    new Date(Date.now() - 48 * 3600 * 1000).toISOString();

  const cols =
    'setup_type,status,opened_at,closed_at,pnl_usd,fees_usd,peak_pnl_pct,exit_reason';

  const [opt, fut, status] = await Promise.all([
    supabase
      .from('paper_options_trades')
      .select(cols)
      .gte('opened_at', since)
      .order('opened_at', { ascending: false })
      .limit(2000),
    supabase
      .from('paper_futures_trades')
      .select(cols)
      .gte('opened_at', since)
      .order('opened_at', { ascending: false })
      .limit(2000),
    supabase
      .from('bot_status')
      .select('bot_state,is_running,is_paused,timestamp')
      .order('created_at', { ascending: false })
      .limit(1),
  ]);

  if (opt.error)
    return NextResponse.json({ error: opt.error.message }, { status: 500 });
  if (fut.error)
    return NextResponse.json({ error: fut.error.message }, { status: 500 });

  return NextResponse.json({
    generated_at: new Date().toISOString(),
    since,
    options: agg(opt.data ?? [], 'pnl_usd'),
    futures: agg(fut.data ?? [], 'pnl_usd'),
    bot: status.data?.[0] ?? null,
  });
}
