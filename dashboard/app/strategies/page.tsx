'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn, formatDuration, formatPnL, getPnLColor } from '@/lib/utils';
import type { Trade } from '@/lib/types';

// The live trader runs ONE strategy. These mirror the constants in
// engine/alpha/live_trader.py and engine/alpha/strategy_v3.py; if a number
// changes there, change it here.
const RULES: { label: string; value: string }[] = [
  { label: 'Gets in', value: 'When a 2-hour candle closes above the highest high, or below the lowest low, of the last 20 candles. Up = long, down = short.' },
  { label: 'Stop-loss', value: '2.5 × ATR from entry. Follows price as the trade moves in our favour, never moves back.' },
  { label: 'Takes profit', value: 'At +25% on the money put in.' },
  { label: 'Safety cap', value: 'Cuts the trade at -26% if price gaps past the stop.' },
  { label: 'Longest hold', value: '72 hours.' },
  { label: 'Size', value: 'About $3 per trade at 10x. Up to 3 trades open at once.' },
  { label: 'Stands down', value: 'If balance drops under $2, or the day is down $3.' },
];

type Window = '7d' | '28d' | '90d' | 'all';
const WINDOWS: { key: Window; label: string; days: number | null }[] = [
  { key: '7d', label: '7 days', days: 7 },
  { key: '28d', label: '28 days', days: 28 },
  { key: '90d', label: '90 days', days: 90 },
  { key: 'all', label: 'All', days: null },
];

function isCurrentStrategy(t: Trade): boolean {
  return (t.setup_type || '').toUpperCase().includes('DONCHIAN');
}

function holdSeconds(t: Trade): number {
  const start = new Date(t.timestamp).getTime();
  const end = t.closed_at ? new Date(t.closed_at).getTime() : Date.now();
  return Number.isFinite(start) && end >= start ? Math.round((end - start) / 1000) : 0;
}

function summarize(list: Trade[]) {
  const wins = list.filter((t) => Number(t.pnl ?? 0) > 0).length;
  const losses = list.filter((t) => Number(t.pnl ?? 0) < 0).length;
  const net = list.reduce((s, t) => s + Number(t.pnl ?? 0), 0);
  const fees = list.reduce((s, t) => s + Number(t.entry_fee ?? 0) + Number(t.exit_fee ?? 0), 0);
  const hold = list.length ? list.reduce((s, t) => s + holdSeconds(t), 0) / list.length : 0;
  return { total: list.length, wins, losses, net, fees, hold, winRate: wins + losses ? (wins / (wins + losses)) * 100 : 0 };
}

export default function StrategiesPage() {
  const { trades, liveSignals } = useSupabase();
  const [win, setWin] = useState<Window>('28d');

  const closed = useMemo(() => {
    const days = WINDOWS.find((w) => w.key === win)?.days ?? null;
    const cutoff = days == null ? 0 : Date.now() - days * 86_400_000;
    return trades
      .filter((t) => t.status === 'closed' && isCurrentStrategy(t))
      .filter((t) => new Date(t.closed_at || t.timestamp).getTime() >= cutoff);
  }, [trades, win]);

  const all = useMemo(() => summarize(closed), [closed]);
  const longs = useMemo(() => summarize(closed.filter((t) => t.position_type !== 'short')), [closed]);
  const shorts = useMemo(() => summarize(closed.filter((t) => t.position_type === 'short')), [closed]);

  const byCoin = useMemo(() => {
    const map = new Map<string, Trade[]>();
    for (const t of closed) {
      const coin = t.pair.split('/')[0];
      map.set(coin, [...(map.get(coin) ?? []), t]);
    }
    return Array.from(map.entries())
      .map(([coin, list]) => ({ coin, ...summarize(list) }))
      .sort((a, b) => b.net - a.net);
  }, [closed]);

  // Which coins the engine will actually trade vs only watch, straight from its scan.
  const { trading, watching } = useMemo(() => {
    const trading: string[] = [];
    const watching: string[] = [];
    for (const s of liveSignals ?? []) {
      if (!s.scan) continue;
      (s.scan.tradeable === false ? watching : trading).push(s.pair.split('/')[0]);
    }
    return { trading: trading.sort(), watching: watching.sort() };
  }, [liveSignals]);

  const maxAbs = Math.max(0.01, ...byCoin.map((c) => Math.abs(c.net)));

  return (
    <div className="space-y-4 pb-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Strategy</h1>
        <p className="mt-1 text-sm text-zinc-500">One strategy is live. This is what it does and how it has done.</p>
      </div>

      {/* What is running */}
      <section className="rounded-xl border border-white/[0.08] bg-[#101114] p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-white">2-hour breakout</h2>
          <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-400">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            In use
          </span>
        </div>
        <p className="mt-1 text-sm text-zinc-400">
          Waits for price to break out of its recent range, then rides the move with a trailing stop.
        </p>

        <dl className="mt-4 divide-y divide-white/[0.06] border-t border-white/[0.06]">
          {RULES.map((r) => (
            <div key={r.label} className="grid grid-cols-[6.5rem_1fr] gap-3 py-2.5 text-sm">
              <dt className="text-zinc-500">{r.label}</dt>
              <dd className="text-zinc-200">{r.value}</dd>
            </div>
          ))}
          <div className="grid grid-cols-[6.5rem_1fr] gap-3 py-2.5 text-sm">
            <dt className="text-zinc-500">Trades</dt>
            <dd className="text-zinc-200">{trading.length ? trading.join(', ') : 'Waiting for scan data'}</dd>
          </div>
          {watching.length > 0 && (
            <div className="grid grid-cols-[6.5rem_1fr] gap-3 py-2.5 text-sm">
              <dt className="text-zinc-500">Only watches</dt>
              <dd className="text-zinc-500">{watching.join(', ')}</dd>
            </div>
          )}
        </dl>
      </section>

      {/* How it has done */}
      <section className="rounded-xl border border-white/[0.08] bg-[#101114]">
        <div className="flex flex-wrap items-center justify-between gap-3 p-4">
          <h2 className="text-base font-semibold text-white">Results</h2>
          <div className="flex gap-1">
            {WINDOWS.map((w) => (
              <button
                key={w.key}
                onClick={() => setWin(w.key)}
                className={cn(
                  'rounded-md px-2.5 py-1.5 text-xs font-medium',
                  win === w.key ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300',
                )}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>

        {all.total === 0 ? (
          <p className="border-t border-white/[0.06] p-6 text-center text-sm text-zinc-500">No closed trades in this period.</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-px border-y border-white/[0.08] bg-white/[0.08] sm:grid-cols-4">
              <Stat label="Net result" value={formatPnL(all.net)} tone={getPnLColor(all.net)} sub={`after $${all.fees.toFixed(2)} fees`} />
              <Stat label="Trades" value={String(all.total)} sub={`${all.wins} won · ${all.losses} lost`} />
              <Stat label="Win rate" value={`${all.winRate.toFixed(0)}%`} sub="of trades that moved" />
              <Stat label="Typical hold" value={formatDuration(all.hold)} sub="per trade" />
            </div>

            <div className="grid grid-cols-2 gap-px border-b border-white/[0.08] bg-white/[0.08]">
              <Stat label="▲ Longs" value={formatPnL(longs.net)} tone={getPnLColor(longs.net)} sub={`${longs.wins} won · ${longs.losses} lost`} />
              <Stat label="▼ Shorts" value={formatPnL(shorts.net)} tone={getPnLColor(shorts.net)} sub={`${shorts.wins} won · ${shorts.losses} lost`} />
            </div>

            <div className="p-4">
              <h3 className="text-xs text-zinc-500">By coin</h3>
              <ul className="mt-2 space-y-2.5">
                {byCoin.map((c) => (
                  <li key={c.coin} className="grid grid-cols-[3.5rem_1fr_auto] items-center gap-3 text-sm">
                    <span className="font-semibold text-white">{c.coin}</span>
                    <div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className={cn('h-full rounded-full', c.net >= 0 ? 'bg-emerald-400' : 'bg-red-400')}
                          style={{ width: `${Math.max(3, (Math.abs(c.net) / maxAbs) * 100)}%` }}
                        />
                      </div>
                      <p className="mt-1 text-[11px] text-zinc-500">{c.wins} won · {c.losses} lost</p>
                    </div>
                    <span className={cn('font-mono text-sm tabular-nums', getPnLColor(c.net))}>{formatPnL(c.net)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}

        <Link href="/trades" className="flex items-center justify-between border-t border-white/[0.06] px-4 py-3 text-sm text-zinc-400 hover:text-white">
          See every trade <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}

function Stat({ label, value, sub, tone = 'text-white' }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="bg-[#101114] p-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className={cn('mt-1 font-mono text-xl font-semibold tabular-nums', tone)}>{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-zinc-500">{sub}</p>}
    </div>
  );
}
