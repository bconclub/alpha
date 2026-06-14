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

// Heat scale: 0% = red (cold/nothing), rising through amber → lime → green as a
// setup closes in on firing. Hue 0 (red) → 138 (green).
function heat(readiness: number): string {
  const r = Math.max(0, Math.min(100, readiness));
  const hue = (r / 100) * 138;
  const light = 44 + (r / 100) * 12;   // brighter as it heats up
  return `hsl(${hue.toFixed(0)} 85% ${light.toFixed(0)}%)`;
}

function levTone(lev: number | null) {
  if (lev === 50) return 'text-red-300 bg-red-500/15 ring-red-500/30';
  if (lev === 25) return 'text-amber-300 bg-amber-500/15 ring-amber-500/30';
  return 'text-emerald-300 bg-emerald-500/15 ring-emerald-500/30';
}

function LaneRow({ lane, leader }: { lane: LiveLaneScan; leader: boolean }) {
  const ready = Math.max(0, Math.min(100, lane.readiness));
  const color = heat(ready);
  const firing = lane.status === 'READY';
  return (
    <div
      className={cn(
        'rounded-xl border px-3 py-2.5 backdrop-blur-md transition-colors',
        leader ? 'border-white/15 bg-white/[0.07]' : 'border-white/5 bg-white/[0.02]',
      )}
      style={leader ? { boxShadow: `0 0 0 1px ${color}22, inset 0 1px 0 rgba(255,255,255,0.05)` } : undefined}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <SetupChip setup={lane.lane} />
          {firing
            ? <span className="text-[10px] font-bold text-emerald-400">▲ {lane.side} — FIRING</span>
            : leader && <span className="text-[9px] font-bold uppercase tracking-wide text-zinc-500">closest</span>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-[11px] text-zinc-500">conf {lane.would_conf.toFixed(0)}</span>
          {lane.would_lev != null && (
            <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-bold ring-1 ring-inset', levTone(lane.would_lev))}>
              {lane.would_lev}x
            </span>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center gap-2.5">
        <div
          className="relative h-2 flex-1 overflow-hidden rounded-full"
          style={{ backgroundImage: 'repeating-linear-gradient(90deg, rgba(255,255,255,0.08) 0 4px, transparent 4px 10px)' }}
        >
          <div
            className={cn('absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out', ready >= 80 && 'animate-pulse')}
            style={{
              width: `${Math.max(ready, 3)}%`,
              background: color,
              // glow grows as the setup heats up → it visibly "lights up" near firing
              boxShadow: `0 0 ${(5 + ready * 0.14).toFixed(0)}px ${color}, 0 0 2px ${color}`,
            }}
          />
        </div>
        <span className="w-9 text-right font-mono text-xs font-semibold tabular-nums" style={{ color }}>
          {ready.toFixed(0)}%
        </span>
      </div>
      <p className="mt-1.5 text-[11px] text-zinc-500">
        {firing ? 'firing now' : 'watching'}: <span className="text-zinc-300">{lane.watching}</span>
      </p>
    </div>
  );
}

// One plain-English line: why is there no trade right now?
function whyNoTrade(scan: LiveSignal['scan'], lanes: LiveLaneScan[], inPos: boolean): { tone: string; text: string } | null {
  if (inPos) return null;                       // there IS a trade — nothing to explain
  if (scan?.status === 'READY') return null;    // firing right now
  const htf = scan?.htf_trend;
  if (htf === 0 || scan?.status === 'FLAT') {
    return { tone: 'text-zinc-400', text: 'No trade — 1h trend is flat (sideways). The bot only enters with the hourly trend.' };
  }
  const top = lanes[0];
  if (!top) return { tone: 'text-zinc-500', text: 'No trade — scanning…' };
  if (top.would_conf < 85) {
    return {
      tone: 'text-amber-300/90',
      text: `No trade — no setup has hit 85 confidence yet. Closest: ${top.name} at conf ${top.would_conf.toFixed(0)} (needs 85).`,
    };
  }
  return {
    tone: 'text-emerald-300/90',
    text: `No trade yet — ${top.name} is armed (conf ${top.would_conf.toFixed(0)}); waiting for price: ${top.watching}.`,
  };
}

function PairCard({ sig }: { sig: LiveSignal }) {
  const base = sig.pair.split('/')[0];
  const scan = sig.scan;
  const pill = statusPill(scan?.status);
  const t = trend(scan?.htf_trend ?? sig.htf_trend);
  const mark = scan?.mark ?? 0;
  const lanes = [...(scan?.lanes ?? [])].sort((a, b) => b.readiness - a.readiness);
  const why = whyNoTrade(scan, lanes, sig.in_position);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.25)]">
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

      {why && (
        <div className={cn('mb-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2 text-[11px]', why.tone)}>
          {why.text}
        </div>
      )}

      {lanes.length === 0 ? (
        <p className="py-4 text-center text-xs text-zinc-600">No scan yet…</p>
      ) : (
        <div className="space-y-2">
          {lanes.map((l, i) => <LaneRow key={l.lane} lane={l} leader={i === 0 && l.readiness > 10} />)}
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
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.3)]">
      <div className="mb-3">
        <h2 className="text-base font-bold text-white">Scanner</h2>
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
