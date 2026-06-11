'use client';

import { useEffect, useState } from 'react';

type LaneStat = { lane: string; n: number; winRate: number; net: number; profitFactor: number };
type LiveTrade = {
  id: number;
  pair: string;
  position_type?: string | null;
  side?: string | null;
  setup_type?: string | null;
  status: string;
  entry_price?: number | null;
  exit_price?: number | null;
  current_price?: number | null;
  leverage?: number | null;
  collateral?: number | null;
  contracts?: number | null;
  stop_loss?: number | null;
  trail_stop_price?: number | null;
  net_pnl?: number | null;
  pnl?: number | null;
  current_pnl?: number | null;
  pnl_pct?: number | null;
  exit_reason?: string | null;
  opened_at: string;
  metadata?: Record<string, unknown> | null;
};
type LivePayload = {
  mirror: { marginUsd: number; leverage: number; minConfidence: number; dailyLossStop: number; killBalance: number; maxOpen: number };
  botStatus: { is_paused?: boolean; delta_balance?: number | null; bot_state?: string | null } | null;
  liveTrades: LiveTrade[];
  liveStats: { n: number; wins: number; winRate: number; net: number; open: number };
  paperLanes: LaneStat[];
};

const num = (v: unknown): number => {
  const n = Number(v ?? 0);
  return Number.isFinite(n) ? n : 0;
};

const LANE_LABELS: Record<string, string> = {
  FUT_EMA_PB_10X: 'EMA Pullback 10x',
  FUT_DONCHIAN_RT_10X: 'Donchian Retest 10x',
  FUT_VWAP_10X: 'VWAP Bounce 10x',
  FUT_EMA_PB_20X: 'EMA 20x (retired)',
  FUT_SFP_15X: 'Liq Sweep (retired)',
};

export default function LiveMirrorPanel() {
  const [data, setData] = useState<LivePayload | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch('/api/live', { cache: 'no-store' });
        if (res.ok && alive) setData(await res.json());
      } catch { /* transient */ }
    };
    load();
    const t = setInterval(load, 15000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!data) return null;

  const bal = num(data.botStatus?.delta_balance);
  const liveOn = data.botStatus?.bot_state === 'live_mirror' || data.liveStats.open > 0 || data.liveStats.n > 0;
  const open = data.liveTrades.filter((t) => t.status === 'open');
  const recent = data.liveTrades.filter((t) => t.status === 'closed').slice(0, 5);
  const activeLanes = data.paperLanes.filter((l) => !LANE_LABELS[l.lane]?.includes('retired'));

  return (
    <div className="bg-[#141419] border border-red-500/20 rounded-xl p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${liveOn ? 'bg-red-500 animate-pulse' : 'bg-zinc-600'}`} />
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-300">Live Mirror — real money</h3>
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${liveOn ? 'bg-red-500/15 text-red-300' : 'bg-zinc-700/40 text-zinc-400'}`}>
            {liveOn ? 'LIVE ON' : 'LIVE OFF'}
          </span>
        </div>
        <div className="font-mono text-sm text-gray-300">
          Delta <span className="font-bold text-white">${bal.toFixed(2)}</span>
          <span className={`ml-3 font-bold ${data.liveStats.net >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {data.liveStats.net >= 0 ? '+' : ''}${data.liveStats.net.toFixed(2)}
          </span>
          <span className="ml-2 text-xs text-gray-500">
            {data.liveStats.n > 0 ? `${data.liveStats.wins}W/${data.liveStats.n - data.liveStats.wins}L (${data.liveStats.winRate.toFixed(0)}%)` : 'no live trades yet'}
          </span>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2 font-mono text-[10px] text-gray-500">
        <span className="rounded border border-white/10 px-1.5 py-0.5">${data.mirror.marginUsd}/trade</span>
        <span className="rounded border border-white/10 px-1.5 py-0.5">{data.mirror.leverage}x</span>
        <span className="rounded border border-white/10 px-1.5 py-0.5">conf ≥{data.mirror.minConfidence}</span>
        <span className="rounded border border-white/10 px-1.5 py-0.5">max {data.mirror.maxOpen} open</span>
        <span className="rounded border border-white/10 px-1.5 py-0.5">day stop {data.mirror.dailyLossStop}$</span>
        <span className="rounded border border-white/10 px-1.5 py-0.5">kill &lt;${data.mirror.killBalance}</span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* live positions / recent live trades */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">Live positions & recent</div>
          {open.length === 0 && recent.length === 0 ? (
            <p className="text-xs text-gray-600 py-2">
              No live trades yet — mirror fires on the next paper signal with conf ≥{data.mirror.minConfidence} from the best lane.
            </p>
          ) : (
            <div className="space-y-1.5">
              {open.map((t) => (
                <div key={t.id} className="flex items-center justify-between rounded border border-red-500/30 bg-red-950/20 px-2 py-1.5 font-mono text-xs">
                  <span>
                    <span className="font-bold text-white">{t.pair?.replace('/USD:USD', '')}</span>{' '}
                    <span className={t.position_type === 'long' ? 'text-green-400' : 'text-red-400'}>{(t.position_type || '').toUpperCase()}</span>{' '}
                    <span className="text-gray-500">{(t.setup_type || '').replace('LIVE_', '')} · {num(t.leverage)}x · ${num(t.collateral).toFixed(2)} in</span>
                  </span>
                  <span>
                    <span className={num(t.current_pnl) >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {num(t.current_pnl) >= 0 ? '+' : ''}${num(t.current_pnl).toFixed(2)}
                    </span>
                    <span className="ml-2 text-red-300">stop {num(t.trail_stop_price || t.stop_loss).toFixed(1)}</span>
                  </span>
                </div>
              ))}
              {recent.map((t) => (
                <div key={t.id} className="flex items-center justify-between rounded border border-white/5 px-2 py-1 font-mono text-[11px] text-gray-400">
                  <span>
                    {t.pair?.replace('/USD:USD', '')} {(t.position_type || '').toUpperCase()}{' '}
                    <span className="text-gray-600">{(t.exit_reason || '').replace(/_/g, ' ')}</span>
                  </span>
                  <span className={num(t.net_pnl ?? t.pnl) >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {num(t.net_pnl ?? t.pnl) >= 0 ? '+' : ''}${num(t.net_pnl ?? t.pnl).toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* paper lane scoreboard the mirror picks from */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">
            Paper lanes (V3 era) — the mirror copies the best of these
          </div>
          <div className="space-y-1">
            {activeLanes.map((l, i) => (
              <div key={l.lane} className="flex items-center justify-between rounded border border-white/5 px-2 py-1 font-mono text-[11px]">
                <span className="text-gray-300">
                  {i === 0 && <span className="mr-1 text-amber-300" title="current best profit factor — the lane the mirror copies">★</span>}
                  {LANE_LABELS[l.lane] || l.lane.replace(/_/g, ' ')}
                </span>
                <span className="text-gray-400">
                  {l.n} trades · {l.winRate.toFixed(0)}% win ·{' '}
                  <span className={l.profitFactor >= 1 ? 'text-green-400 font-bold' : 'text-gray-300'}>PF {l.profitFactor.toFixed(2)}</span>
                  <span className={`ml-2 ${l.net >= 0 ? 'text-green-400' : 'text-red-400'}`}>{l.net >= 0 ? '+' : ''}${l.net.toFixed(0)}</span>
                </span>
              </div>
            ))}
            {activeLanes.length === 0 && <p className="text-xs text-gray-600">No closed paper trades this era yet.</p>}
          </div>
          <p className="mt-1.5 text-[10px] text-gray-600">Gate to scale up: a lane holding PF &gt; 1.0 over ~200 trades.</p>
        </div>
      </div>
    </div>
  );
}
