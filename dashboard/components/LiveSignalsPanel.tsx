'use client';

import { useSupabase } from '@/components/providers/SupabaseProvider';
import { SetupChip } from '@/components/ui/SetupChip';
import { cn } from '@/lib/utils';
import type { LiveSignal } from '@/lib/types';

const PREFERRED_ORDER = ['BTC/USD:USD', 'ETH/USD:USD'];

function trendLabel(htf: number | null): { icon: string; text: string; cls: string } {
  if (htf === 1) return { icon: '↗', text: '1h up', cls: 'text-emerald-400' };
  if (htf === -1) return { icon: '↘', text: '1h down', cls: 'text-red-400' };
  return { icon: '→', text: '1h flat', cls: 'text-zinc-500' };
}

function levTone(lev: number | null): string {
  if (lev === 50) return 'text-red-300 bg-red-500/15 ring-red-500/30';
  if (lev === 25) return 'text-amber-300 bg-amber-500/15 ring-amber-500/30';
  return 'text-emerald-300 bg-emerald-500/15 ring-emerald-500/30';
}

function Row({ s }: { s: LiveSignal }) {
  const base = s.pair.split('/')[0];
  const hasSignal = !!s.direction && s.confidence >= 85;
  const trend = trendLabel(s.htf_trend);
  const long = s.direction === 'long';

  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-white/[0.03] px-3 py-2.5">
      <div className="flex items-center gap-2.5 min-w-0">
        <span className="font-mono text-sm font-bold text-white w-9">{base}</span>
        {hasSignal ? (
          <>
            <SetupChip setup={s.lane} />
            <span className={cn('text-xs font-bold', long ? 'text-emerald-400' : 'text-red-400')}>
              {long ? '▲ LONG' : '▼ SHORT'}
            </span>
          </>
        ) : (
          <span className="text-xs text-zinc-500">No setup — waiting</span>
        )}
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <span className={cn('text-[11px] font-medium', trend.cls)}>{trend.icon} {trend.text}</span>
        {hasSignal && (
          <>
            <span className="font-mono text-xs text-zinc-300">{s.confidence.toFixed(0)}%</span>
            {s.would_lev != null && (
              <span className={cn('rounded-md px-1.5 py-0.5 text-[10px] font-bold ring-1 ring-inset', levTone(s.would_lev))}>
                {s.would_lev}x
              </span>
            )}
          </>
        )}
        {s.in_position && (
          <span className="rounded-md bg-violet-500/15 px-1.5 py-0.5 text-[10px] font-bold text-violet-300 ring-1 ring-inset ring-violet-500/30">
            IN TRADE
          </span>
        )}
      </div>
    </div>
  );
}

export default function LiveSignalsPanel() {
  const { liveSignals } = useSupabase();

  const rows = [...(liveSignals ?? [])].sort((a, b) => {
    const ia = PREFERRED_ORDER.indexOf(a.pair);
    const ib = PREFERRED_ORDER.indexOf(b.pair);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  return (
    <div className="rounded-2xl border border-white/5 bg-[#141419] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">Live Signals 📡</h3>
          <p className="text-[11px] text-zinc-500">What the autonomous trader sees right now · conf ≥ 85 trades, leverage by conviction</p>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="px-1 py-6 text-center text-xs text-zinc-600">No signal data yet — engine publishes every ~12s.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((s) => <Row key={s.pair} s={s} />)}
        </div>
      )}
    </div>
  );
}
