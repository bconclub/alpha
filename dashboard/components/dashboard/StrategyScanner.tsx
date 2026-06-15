'use client';

import { useSupabase } from '@/components/providers/SupabaseProvider';
import { SetupChip } from '@/components/ui/SetupChip';
import { cn } from '@/lib/utils';
import type { LiveSignal } from '@/lib/types';

const TOP_N = 7;
const DOTS = 16;

// Per-strategy color — so the board isn't a wall of one color.
const LANE_COLOR: Record<string, string> = {
  FUT_EMA_PB: '#22d3ee',       // cyan
  FUT_DONCHIAN_RT: '#a78bfa',  // violet
  FUT_VWAP: '#f59e0b',         // amber
};
function laneColor(lane: string): string {
  return LANE_COLOR[lane] ?? '#38bdf8';
}

// Per-leverage color.
function levTone(lev: number | null) {
  if (lev === 50) return 'text-red-300 bg-red-500/15 ring-red-500/30';
  if (lev === 25) return 'text-amber-300 bg-amber-500/15 ring-amber-500/30';
  if (lev === 10) return 'text-emerald-300 bg-emerald-500/15 ring-emerald-500/30';
  return 'text-zinc-300 bg-zinc-500/15 ring-zinc-500/30';
}

// Coin badge — brand-colored, glyph or ticker initial.
const COIN: Record<string, { bg: string; glyph: string }> = {
  BTC: { bg: '#f7931a', glyph: '₿' }, ETH: { bg: '#627eea', glyph: 'Ξ' },
  SOL: { bg: 'linear-gradient(135deg,#9945FF,#14F195)', glyph: '◎' }, XRP: { bg: '#3a3f45', glyph: '✕' },
  DOGE: { bg: '#c2a633', glyph: 'Ð' }, AVAX: { bg: '#e84142', glyph: 'A' },
  LINK: { bg: '#2a5ada', glyph: '⬡' }, BNB: { bg: '#f3ba2f', glyph: 'B' },
  ADA: { bg: '#0033ad', glyph: '₳' }, LTC: { bg: '#345d9d', glyph: 'Ł' },
  SUI: { bg: '#4da2ff', glyph: 'S' }, AAVE: { bg: '#b6509e', glyph: 'A' },
};
function CoinBadge({ asset }: { asset: string }) {
  const c = COIN[asset] ?? { bg: '#3f3f46', glyph: asset.slice(0, 1) };
  return (
    <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[12px] font-bold text-white ring-1 ring-white/15"
      style={{ background: c.bg }}>{c.glyph}</span>
  );
}

type Row = {
  key: string; asset: string; lane: string; name: string; side: string;
  readiness: number; conf: number; lev: number | null; watching: string;
  firing: boolean; inPos: boolean; tradeable: boolean;
};

function flatten(signals: LiveSignal[]): Row[] {
  const rows: Row[] = [];
  for (const sig of signals) {
    const asset = sig.pair.split('/')[0];
    const scan = sig.scan;
    if (!scan) continue;
    for (const l of scan.lanes ?? []) {
      const tradeable = scan.tradeable !== false;
      rows.push({
        key: `${asset}:${l.lane}`, asset, lane: l.lane, name: l.name, side: l.side,
        readiness: Math.max(0, Math.min(100, l.readiness)), conf: l.would_conf, lev: l.would_lev,
        watching: l.watching, firing: tradeable && scan.status === 'READY' && sig.lane === l.lane,
        inPos: !!scan.in_position, tradeable,
      });
    }
  }
  rows.sort((a, b) => (Number(b.firing) - Number(a.firing)) || (b.readiness - a.readiness));
  return rows;
}

// Red → amber → green across the meter: each dot is colored by its POSITION,
// so a filling meter reads as a trigger sequence (cold on the left, hot near firing).
function heat(pct: number): string {
  const r = Math.max(0, Math.min(100, pct));
  return `hsl(${((r / 100) * 138).toFixed(0)} 85% 52%)`;
}
function DotMeter({ readiness, dim }: { readiness: number; dim: boolean }) {
  const filled = Math.round((readiness / 100) * DOTS);
  return (
    <div className="flex flex-1 items-center gap-[3px]">
      {Array.from({ length: DOTS }).map((_, i) => {
        const on = i < filled;
        const c = heat((i / (DOTS - 1)) * 100);
        return (
          <span
            key={i}
            className="h-1.5 flex-1 rounded-full transition-colors"
            style={{
              background: on ? c : 'rgba(255,255,255,0.08)',
              opacity: on && dim ? 0.65 : 1,
              boxShadow: on && !dim && i === filled - 1 ? `0 0 6px ${c}` : undefined,
            }}
          />
        );
      })}
    </div>
  );
}

function SignalRow({ r, rank }: { r: Row; rank: number }) {
  const color = laneColor(r.lane);
  const top = rank === 0;
  const long = r.side === 'LONG';
  const arrow = long ? '▲' : r.side === 'SHORT' ? '▼' : '·';
  // fade rows down the list — only the top one is at full strength
  const opacity = top ? 1 : Math.max(0.4, 1 - rank * 0.11);

  return (
    <div
      className={cn(
        'flex flex-1 flex-col justify-center rounded-xl border px-3 py-2.5 backdrop-blur-md transition-all',
        top ? 'border-white/20 bg-white/[0.07]' : 'border-white/5 bg-white/[0.02]',
      )}
      style={{ opacity, boxShadow: top ? `0 0 0 1px ${color}33` : undefined }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <CoinBadge asset={r.asset} />
          <span className="font-mono text-sm font-bold text-white">{r.asset}</span>
          <SetupChip setup={r.lane} />
          <span className={cn('text-[10px] font-bold', long ? 'text-emerald-400' : r.side === 'SHORT' ? 'text-red-400' : 'text-zinc-500')}>
            {arrow} {r.side}
          </span>
          {!r.tradeable && <span className="rounded bg-zinc-600/30 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-zinc-400">watch</span>}
          {r.tradeable && top && !r.firing && <span className="rounded bg-white/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-zinc-300">next to fire</span>}
          {r.firing && <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-300">FIRING</span>}
          {r.inPos && <span className="rounded bg-violet-500/15 px-1.5 py-0.5 text-[9px] font-bold text-violet-300">IN TRADE</span>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="font-mono text-[11px] text-zinc-500">conf {r.conf.toFixed(0)}</span>
          {r.lev != null && (
            <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-bold ring-1 ring-inset', levTone(r.lev))}>{r.lev}x</span>
          )}
        </div>
      </div>

      <div className="mt-2 flex items-center gap-2.5">
        <DotMeter readiness={r.readiness} dim={!top} />
        <span className="w-9 text-right font-mono text-xs font-semibold tabular-nums" style={{ color: heat(r.readiness) }}>
          {r.readiness.toFixed(0)}%
        </span>
      </div>

      <p className="mt-1.5 truncate text-[11px] text-zinc-500">
        {r.firing ? 'firing now' : 'watching'}: <span className="text-zinc-300">{r.watching}</span>
      </p>
    </div>
  );
}

export function StrategyScanner() {
  const { liveSignals } = useSupabase();
  const all = flatten(liveSignals ?? []);
  const rows = all.slice(0, TOP_N);
  const assetCount = new Set(all.map((r) => r.asset)).size;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.3)]">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-bold text-white">Scanner</h2>
        <span className="text-[11px] text-zinc-500">{assetCount} assets · top {TOP_N}</span>
      </div>

      {rows.length === 0 ? (
        <p className="flex flex-1 items-center justify-center text-center text-xs text-zinc-600">No signal data yet — engine publishes every ~12s.</p>
      ) : (
        <div className="flex flex-1 flex-col gap-2">
          {rows.map((r, i) => <SignalRow key={r.key} r={r} rank={i} />)}
        </div>
      )}
    </div>
  );
}
