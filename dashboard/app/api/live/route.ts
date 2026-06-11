import { NextResponse } from 'next/server';
import { getServerSupabase } from '@/lib/supabase-server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// V3 era start — paper lane stats shown to explain what the LiveMirror picks from.
const ERA_START = '2026-06-09T21:21:00Z';

// LiveMirror rails (mirrors engine/alpha/live_mirror.py constants — display only).
const MIRROR = {
  marginUsd: 5,
  leverage: 10,
  minConfidence: 85,
  dailyLossStop: -3,
  killBalance: 20,
  maxOpen: 1,
};

export async function GET() {
  const supabase = getServerSupabase();
  if (!supabase) {
    return NextResponse.json({ error: 'Server Supabase client is not configured.' }, { status: 500 });
  }

  const [liveTradesRes, statusRes, paperRes] = await Promise.all([
    supabase
      .from('trades')
      .select('*')
      .eq('strategy', 'live_mirror')
      .order('opened_at', { ascending: false })
      .limit(50),
    supabase
      .from('bot_status')
      .select('bot_state,is_paused,delta_balance,created_at,market_regime')
      .order('created_at', { ascending: false })
      .limit(1),
    supabase
      .from('paper_futures_trades')
      .select('setup_type,status,pnl_usd,metadata')
      .eq('status', 'closed')
      .gte('opened_at', ERA_START)
      .limit(2000),
  ]);

  // Per-lane paper stats: what the mirror selects from + each lane's win rate / PF.
  const lanes: Record<string, { n: number; wins: number; net: number; grossWin: number; grossLoss: number }> = {};
  for (const r of paperRes.data ?? []) {
    const k = r.setup_type || '?';
    const p = Number(r.pnl_usd ?? 0);
    lanes[k] = lanes[k] || { n: 0, wins: 0, net: 0, grossWin: 0, grossLoss: 0 };
    lanes[k].n += 1;
    lanes[k].net += p;
    if (p > 0) { lanes[k].wins += 1; lanes[k].grossWin += p; } else { lanes[k].grossLoss -= p; }
  }
  const paperLanes = Object.entries(lanes)
    .map(([lane, s]) => ({
      lane,
      n: s.n,
      winRate: s.n ? (100 * s.wins) / s.n : 0,
      net: s.net,
      profitFactor: s.grossLoss > 0 ? s.grossWin / s.grossLoss : (s.grossWin > 0 ? 2 : 0),
    }))
    .sort((a, b) => b.profitFactor - a.profitFactor);

  const live = liveTradesRes.data ?? [];
  const realized = live.filter((t) => t.status === 'closed');
  const liveNet = realized.reduce((s, t) => s + Number(t.net_pnl ?? t.pnl ?? 0), 0);
  const liveWins = realized.filter((t) => Number(t.net_pnl ?? t.pnl ?? 0) > 0).length;

  return NextResponse.json({
    mirror: MIRROR,
    botStatus: statusRes.data?.[0] ?? null,
    liveTrades: live,
    liveStats: {
      n: realized.length,
      wins: liveWins,
      winRate: realized.length ? (100 * liveWins) / realized.length : 0,
      net: liveNet,
      open: live.filter((t) => t.status === 'open').length,
    },
    paperLanes,
  });
}
