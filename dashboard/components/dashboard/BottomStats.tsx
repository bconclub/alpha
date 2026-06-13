'use client';

import { useMemo } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn, formatCurrency } from '@/lib/utils';

/** Tiny sparkline from a number series. */
function Spark({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) return <div className="h-8" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 96, h = 32;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / span) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/** Open-positions donut: winning (emerald) vs the rest (violet). */
function Donut({ total, winning }: { total: number; winning: number }) {
  const r = 16, c = 2 * Math.PI * r;
  const frac = total > 0 ? winning / total : 0;
  return (
    <svg width={44} height={44} viewBox="0 0 44 44">
      <circle cx="22" cy="22" r={r} fill="none" stroke="#a78bfa" strokeWidth={5} opacity={0.5} />
      <circle
        cx="22" cy="22" r={r} fill="none" stroke="#34d399" strokeWidth={5}
        strokeDasharray={`${(c * frac).toFixed(1)} ${c.toFixed(1)}`}
        strokeLinecap="round" transform="rotate(-90 22 22)"
      />
      <text x="22" y="26" textAnchor="middle" className="fill-white" style={{ fontSize: 13, fontWeight: 700 }}>{total}</text>
    </svg>
  );
}

function Card({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/5 bg-[#141419] p-4">
      <p className="text-[11px] uppercase tracking-wider text-zinc-500">{label}</p>
      <div className="mt-2 flex items-end justify-between gap-2">{children}</div>
    </div>
  );
}

export function BottomStats() {
  const { botStatus, trades, dailyPnL } = useSupabase();

  const stats = useMemo(() => {
    const closed = trades.filter((t) => t.status === 'closed');
    const open = trades.filter((t) => t.status === 'open');
    const winningOpen = open.filter((t) => Number(t.current_pnl ?? 0) > 0).length;

    // last 20 closed → win rate + a rolling-winrate sparkline
    const last20 = closed.slice(0, 20).reverse();
    const wins20 = last20.filter((t) => Number(t.pnl ?? 0) > 0).length;
    const winRate = last20.length ? (wins20 / last20.length) * 100 : (botStatus?.win_rate ?? 0);
    const rolling: number[] = [];
    let w = 0;
    last20.forEach((t, i) => { if (Number(t.pnl ?? 0) > 0) w += 1; rolling.push((w / (i + 1)) * 100); });

    // 24h P&L + a cumulative spark over the day's closed trades
    const since = Date.now() - 24 * 3600_000;
    const today = closed.filter((t) => new Date(t.closed_at ?? t.timestamp).getTime() >= since)
      .sort((a, b) => new Date(a.closed_at ?? a.timestamp).getTime() - new Date(b.closed_at ?? b.timestamp).getTime());
    let cum = 0; const pnlSpark = today.map((t) => (cum += Number(t.pnl ?? 0)));
    const pnl24 = cum;

    // daily pnl series (cumulative) for the portfolio-delta spark
    const dailySeries: number[] = [];
    let dc = 0;
    [...dailyPnL].forEach((d) => { dc += Number(d.daily_pnl ?? 0); dailySeries.push(dc); });

    const delta = Number(botStatus?.delta_balance ?? botStatus?.capital ?? 0);
    const capital = Number(botStatus?.capital ?? delta);

    return {
      delta, deltaSpark: dailySeries.length > 1 ? dailySeries : [0, delta],
      openCount: open.length, winningOpen,
      winRate, rolling: rolling.length > 1 ? rolling : [winRate, winRate],
      pnl24, pnlSpark: pnlSpark.length > 1 ? pnlSpark : [0, pnl24],
      capital,
    };
  }, [botStatus, trades, dailyPnL]);

  const pnlUp = stats.pnl24 >= 0;

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
      <Card label="Portfolio Value">
        <div>
          <div className="font-mono text-2xl font-bold text-white">{formatCurrency(stats.delta)}</div>
          <p className="mt-0.5 text-[11px] text-emerald-400">Delta · live</p>
        </div>
        <Spark values={stats.deltaSpark} color="#34d399" />
      </Card>

      <Card label="Open Positions">
        <div>
          <div className="font-mono text-2xl font-bold text-white">{stats.openCount}</div>
          <p className="mt-0.5 text-[11px] text-zinc-400">{stats.winningOpen} winning</p>
        </div>
        <Donut total={stats.openCount} winning={stats.winningOpen} />
      </Card>

      <Card label="Win Rate">
        <div>
          <div className="font-mono text-2xl font-bold text-white">{stats.winRate.toFixed(0)}%</div>
          <p className="mt-0.5 text-[11px] text-zinc-400">Last 20 trades</p>
        </div>
        <Spark values={stats.rolling} color="#34d399" />
      </Card>

      <Card label="Total P/L (24h)">
        <div>
          <div className={cn('font-mono text-2xl font-bold', pnlUp ? 'text-emerald-400' : 'text-red-400')}>
            {pnlUp ? '+' : '−'}{formatCurrency(Math.abs(stats.pnl24))}
          </div>
          <p className={cn('mt-0.5 text-[11px]', pnlUp ? 'text-emerald-400' : 'text-red-400')}>
            {stats.capital > 0 ? `${pnlUp ? '+' : '−'}${Math.abs((stats.pnl24 / stats.capital) * 100).toFixed(2)}%` : '—'}
          </p>
        </div>
        <Spark values={stats.pnlSpark} color={pnlUp ? '#34d399' : '#f87171'} />
      </Card>

      <Card label="Capital">
        <div className="w-full">
          <div className="font-mono text-2xl font-bold text-white">{formatCurrency(stats.capital)}</div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
            <div className="h-full rounded-full bg-sky-400" style={{ width: '100%' }} />
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">deployed on Delta</p>
        </div>
      </Card>
    </div>
  );
}
