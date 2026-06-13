'use client';

import { useSupabase } from '@/components/providers/SupabaseProvider';
import { SetupChip } from '@/components/ui/SetupChip';
import { cn } from '@/lib/utils';
import type { LiveSignal, LiveLaneScan } from '@/lib/types';

const ORDER = ['BTC/USD:USD', 'ETH/USD:USD'];

function statusPill(status: string | undefined) {
  switch (status) {
    case 'READY': return { label: 'READY', cls: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30' };
    case 'CLOSE': return { label: 'CLOSING IN', cls: 'bg-amber-500/15 text-amber-300 ring-amber-500/30' };
    case 'FLAT': return { label: '1H FLAT', cls: 'bg-zinc-600/30 text-zinc-400 ring-zinc-600/40' };
    default: return { label: 'SCANNING', cls: 'bg-sky-500/15 text-sky-300 ring-sky-500/30' };
  }
}

function trend(htf: number | null | undefined) {
  if (htf === 1) return { icon: '↗', text: '1h up', cls: 'text-emerald-400' };
  if (htf === -1) return { icon: '↘', text: '1h down', cls: 'text-red-400' };
  return { icon: '→', text: '1h flat', cls: 'text-zinc-500' };
}

function barColor(status: string) {
  if (status === 'READY') return 'bg-emerald-400';
  if (status === 'CLOSE') return 'bg-amber-400';
  if (status === 'SCANNING') return 'bg-sky-400';
  return 'bg-zinc-600';
}

function levTone(lev: number | null) {
  if (lev === 50) return 'text-red-300 bg-red-500/15 ring-red-500/30';
  if (lev === 25) return 'text-amber-300 bg-amber-500/15 ring-amber-500/30';
  return 'text-emerald-300 bg-emerald-500/15 ring-emerald-500/30';
}

function LaneRow({ lane }: { lane: LiveLaneScan }) {
  const ready = Math.max(0, Math.min(100, lane.readiness));
  return (
    <div className="rounded-lg bg-black/20 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <SetupChip setup={lane.lane} />
          {lane.status === 'READY' && (
            <span className="text-[10px] font-bold text-emerald-400">▲ {lane.side}</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-[11px] text-zinc-400">conf {lane.would_conf.toFixed(0)}</span>
          {lane.would_lev != null && (
            <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-bold ring-1 ring-inset', levTone(lane.would_lev))}>
              {lane.would_lev}x
            </span>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
          <div className={cn('h-full rounded-full transition-all duration-500', barColor(lane.status))} style={{ width: `${ready}%` }} />
        </div>
        <span className="w-9 text-right font-mono text-[11px] text-zinc-300">{ready.toFixed(0)}%</span>
      </div>
      <p className="mt-1.5 text-[11px] text-zinc-500">
        {lane.status === 'READY' ? 'firing now' : 'watching'}: <span className="text-zinc-400">{lane.watching}</span>
      </p>
    </div>
  );
}

function PairCard({ sig }: { sig: LiveSignal }) {
  const base = sig.pair.split('/')[0];
  const scan = sig.scan;
  const pill = statusPill(scan?.status);
  const t = trend(scan?.htf_trend ?? sig.htf_trend);
  const mark = scan?.mark ?? 0;
  const lanes = [...(scan?.lanes ?? [])].sort((a, b) => b.readiness - a.readiness);

  return (
    <div className="rounded-xl border border-white/5 bg-[#16161c] p-4">
      <div className="mb-3 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-white">{base}</span>
            {mark > 0 && <span className="font-mono text-sm text-zinc-400">${mark.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>}
          </div>
          <span className={cn('mt-0.5 inline-block text-[11px] font-medium', t.cls)}>{t.icon} {t.text}</span>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className={cn('rounded-md px-2 py-0.5 text-[10px] font-bold ring-1 ring-inset', pill.cls)}>{pill.label}</span>
          {sig.in_position && (
            <span className="rounded-md bg-violet-500/15 px-1.5 py-0.5 text-[10px] font-bold text-violet-300 ring-1 ring-inset ring-violet-500/30">IN TRADE</span>
          )}
        </div>
      </div>

      {lanes.length === 0 ? (
        <p className="py-4 text-center text-xs text-zinc-600">No scan yet…</p>
      ) : (
        <div className="space-y-2">
          {lanes.map((l) => <LaneRow key={l.lane} lane={l} />)}
        </div>
      )}
    </div>
  );
}

export function StrategyScanner() {
  const { liveSignals } = useSupabase();
  const rows = [...(liveSignals ?? [])].sort((a, b) => {
    const ia = ORDER.indexOf(a.pair); const ib = ORDER.indexOf(b.pair);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  return (
    <div className="rounded-2xl border border-white/5 bg-[#141419] p-4">
      <div className="mb-3">
        <h2 className="text-base font-bold text-white">Strategy Scanner 🎯</h2>
        <p className="text-[11px] text-zinc-500">Live V3 entry hunt — how close each setup is, the level it&apos;s watching, and the leverage it would take. Fires at conf ≥ 85, 1h-aligned.</p>
      </div>
      {rows.length === 0 ? (
        <p className="py-8 text-center text-xs text-zinc-600">No signal data yet — engine publishes every ~12s.</p>
      ) : (
        <div className="space-y-3">
          {rows.map((s) => <PairCard key={s.pair} sig={s} />)}
        </div>
      )}
    </div>
  );
}
