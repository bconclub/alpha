'use client';

import { useSupabase } from '@/components/providers/SupabaseProvider';
import { SetupChip } from '@/components/ui/SetupChip';
import { cn } from '@/lib/utils';
import type { LiveSignal } from '@/lib/types';

// Heat scale: 0% = red (cold), rising through amber → green as a setup nears firing.
function heat(readiness: number): string {
  const r = Math.max(0, Math.min(100, readiness));
  const hue = (r / 100) * 138;
  const light = 44 + (r / 100) * 12;
  return `hsl(${hue.toFixed(0)} 85% ${light.toFixed(0)}%)`;
}

function levTone(lev: number | null) {
  if (lev === 50) return 'text-red-300 bg-red-500/15 ring-red-500/30';
  if (lev === 25) return 'text-amber-300 bg-amber-500/15 ring-amber-500/30';
  return 'text-emerald-300 bg-emerald-500/15 ring-emerald-500/30';
}

// One flattened setup across the whole board: asset × lane.
type Row = {
  key: string;
  asset: string;
  lane: string;
  name: string;
  side: string;          // LONG | SHORT | —
  htf: number | null;
  readiness: number;
  conf: number;
  lev: number | null;
  watching: string;
  firing: boolean;       // this exact lane is the one firing
  inPos: boolean;        // the asset has an open position
};

function flatten(signals: LiveSignal[]): Row[] {
  const rows: Row[] = [];
  for (const sig of signals) {
    const asset = sig.pair.split('/')[0];
    const scan = sig.scan;
    if (!scan) continue;
    const firingLane = sig.lane;       // best/firing lane for this asset (if any)
    for (const l of scan.lanes ?? []) {
      rows.push({
        key: `${asset}:${l.lane}`,
        asset,
        lane: l.lane,
        name: l.name,
        side: l.side,
        htf: scan.htf_trend,
        readiness: Math.max(0, Math.min(100, l.readiness)),
        conf: l.would_conf,
        lev: l.would_lev,
        watching: l.watching,
        firing: scan.status === 'READY' && firingLane === l.lane,
        inPos: !!scan.in_position,
      });
    }
  }
  // Hottest first: firing on top, then by readiness.
  rows.sort((a, b) => (Number(b.firing) - Number(a.firing)) || (b.readiness - a.readiness));
  return rows;
}

function SignalRow({ r, rank }: { r: Row; rank: number }) {
  const color = heat(r.readiness);
  const long = r.side === 'LONG';
  const arrow = r.side === 'LONG' ? '▲' : r.side === 'SHORT' ? '▼' : '·';
  return (
    <div
      className={cn(
        'rounded-xl border px-3 py-2.5 backdrop-blur-md transition-colors',
        r.firing ? 'border-emerald-400/30 bg-emerald-400/[0.06]'
          : rank === 0 ? 'border-white/15 bg-white/[0.06]' : 'border-white/5 bg-white/[0.02]',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="w-12 shrink-0 font-mono text-sm font-bold text-white">{r.asset}</span>
          <SetupChip setup={r.lane} />
          <span className={cn('text-[10px] font-bold', long ? 'text-emerald-400' : r.side === 'SHORT' ? 'text-red-400' : 'text-zinc-500')}>
            {arrow} {r.side}
          </span>
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
        <div
          className="relative h-2 flex-1 overflow-hidden rounded-full"
          style={{ backgroundImage: 'repeating-linear-gradient(90deg, rgba(255,255,255,0.08) 0 4px, transparent 4px 10px)' }}
        >
          <div
            className={cn('absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out', r.readiness >= 80 && 'animate-pulse')}
            style={{ width: `${Math.max(r.readiness, 3)}%`, background: color, boxShadow: `0 0 ${(5 + r.readiness * 0.14).toFixed(0)}px ${color}, 0 0 2px ${color}` }}
          />
        </div>
        <span className="w-9 text-right font-mono text-xs font-semibold tabular-nums" style={{ color }}>{r.readiness.toFixed(0)}%</span>
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
  // Show the ones that matter (closing in), but always keep at least the top 8.
  const hot = all.filter((r) => r.firing || r.inPos || r.readiness >= 12);
  const rows = (hot.length >= 8 ? hot : all.slice(0, 8));
  const assetCount = new Set(all.map((r) => r.asset)).size;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.3)]">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-bold text-white">Scanner</h2>
        <span className="text-[11px] text-zinc-500">{assetCount} assets · top setups first</span>
      </div>

      {rows.length === 0 ? (
        <p className="py-8 text-center text-xs text-zinc-600">No signal data yet — engine publishes every ~12s.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((r, i) => <SignalRow key={r.key} r={r} rank={i} />)}
        </div>
      )}
    </div>
  );
}
