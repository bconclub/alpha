'use client';

import { useMemo, useState } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn } from '@/lib/utils';

type Win = '1H' | '24H' | '7D' | '30D';
const WINDOWS: { key: Win; hours: number }[] = [
  { key: '1H', hours: 1 },
  { key: '24H', hours: 24 },
  { key: '7D', hours: 24 * 7 },
  { key: '30D', hours: 24 * 30 },
];

type Point = { t: number; label: string; btc: number | null; eth: number | null; vol: number | null };

function fmtTime(ts: number, win: Win): string {
  const d = new Date(ts);
  if (win === '1H' || win === '24H') {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export function MarketSentiment() {
  const { strategyLog } = useSupabase();
  const [win, setWin] = useState<Win>('24H');

  const data = useMemo<Point[]>(() => {
    const cutoff = Date.now() - WINDOWS.find((w) => w.key === win)!.hours * 3600_000;
    // bucket strategy_log rows by minute → { btc, eth, vol } per bucket
    const buckets = new Map<number, { btc?: number; eth?: number; volSum: number; volN: number }>();
    for (const row of strategyLog) {
      const ts = new Date(row.timestamp).getTime();
      if (!Number.isFinite(ts) || ts < cutoff) continue;
      const price = Number(row.current_price ?? 0);
      if (price <= 0) continue;
      const base = (row.pair || '').split('/')[0];
      const bucket = Math.floor(ts / 60_000) * 60_000;
      const b = buckets.get(bucket) ?? { volSum: 0, volN: 0 };
      if (base === 'BTC') b.btc = price;
      else if (base === 'ETH') b.eth = price;
      const atr = Number(row.atr ?? 0);
      if (atr > 0 && price > 0) { b.volSum += (atr / price) * 100; b.volN += 1; }
      buckets.set(bucket, b);
    }
    const sorted = Array.from(buckets.entries()).sort((a, b) => a[0] - b[0]);
    if (sorted.length === 0) return [];
    // rebase BTC & ETH to % change from the first available value in the window
    let btc0 = 0, eth0 = 0;
    for (const [, b] of sorted) { if (!btc0 && b.btc) btc0 = b.btc; if (!eth0 && b.eth) eth0 = b.eth; if (btc0 && eth0) break; }
    return sorted.map(([t, b]) => ({
      t,
      label: fmtTime(t, win),
      btc: b.btc && btc0 ? ((b.btc - btc0) / btc0) * 100 : null,
      eth: b.eth && eth0 ? ((b.eth - eth0) / eth0) * 100 : null,
      vol: b.volN ? b.volSum / b.volN : null,
    }));
  }, [strategyLog, win]);

  const hasData = data.length > 1;

  return (
    <div className="rounded-2xl border border-white/5 bg-[#141419] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-gray-400">Market Sentiment &amp; Volatility</h2>
          <div className="mt-1 flex items-center gap-3 text-[11px]">
            <span className="flex items-center gap-1.5 text-zinc-400"><span className="h-2 w-2 rounded-full bg-orange-400" /> BTC</span>
            <span className="flex items-center gap-1.5 text-zinc-400"><span className="h-2 w-2 rounded-full bg-violet-400" /> ETH</span>
            <span className="flex items-center gap-1.5 text-zinc-500"><span className="h-2 w-2 rounded-sm bg-sky-500/40" /> Volatility</span>
            <span className="text-zinc-600">· moves indexed to window start</span>
          </div>
        </div>
        <div className="flex gap-1">
          {WINDOWS.map(({ key }) => (
            <button
              key={key}
              onClick={() => setWin(key)}
              className={cn(
                'rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors',
                win === key ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300',
              )}
            >
              {key}
            </button>
          ))}
        </div>
      </div>

      {!hasData ? (
        <div className="flex h-[260px] items-center justify-center text-xs text-zinc-600">
          Not enough history for this window yet.
        </div>
      ) : (
        <div className="h-[260px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -8 }}>
              <defs>
                <linearGradient id="volFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
              <XAxis dataKey="label" tick={{ fill: '#71717a', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={40} />
              <YAxis yAxisId="px" tick={{ fill: '#71717a', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`} width={48} />
              <YAxis yAxisId="vol" orientation="right" tick={{ fill: '#52525b', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v.toFixed(1)}%`} width={36} />
              <Tooltip
                contentStyle={{ background: '#0c0c10', border: '1px solid #ffffff14', borderRadius: 10, fontSize: 12 }}
                labelStyle={{ color: '#a1a1aa' }}
                formatter={((val: number, name: string) => [
                  name === 'Volatility' ? `${val.toFixed(2)}%` : `${val > 0 ? '+' : ''}${val.toFixed(2)}%`,
                  name,
                ]) as never}
              />
              <Area yAxisId="vol" type="monotone" dataKey="vol" name="Volatility" stroke="#38bdf8" strokeOpacity={0.4} fill="url(#volFill)" strokeWidth={1} dot={false} connectNulls />
              <Line yAxisId="px" type="monotone" dataKey="btc" name="BTC" stroke="#fb923c" strokeWidth={2} dot={false} connectNulls />
              <Line yAxisId="px" type="monotone" dataKey="eth" name="ETH" stroke="#a78bfa" strokeWidth={2} dot={false} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
