'use client';

import { useMemo, useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn, formatCurrency } from '@/lib/utils';

type TF = '24H' | '7D' | '14D' | '30D';
// Calendar-day windows (local midnight). 24H = TODAY (yesterday-midnight→tonight),
// not a rolling 24h — so Total P/L (24H) matches the "Today" detail exactly.
const TF_DAYS: Record<TF, number> = { '24H': 1, '7D': 7, '14D': 14, '30D': 30 };
function windowCutoff(tf: TF): number {
  const mid = new Date();
  mid.setHours(0, 0, 0, 0);
  return mid.getTime() - (TF_DAYS[tf] - 1) * 86400_000;
}

function Spark({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) return <div className="h-8 w-24" />;
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const w = 96, h = 32;
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - ((v - min) / span) * h).toFixed(1)}`).join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function Donut({ total, winning }: { total: number; winning: number }) {
  const r = 16, c = 2 * Math.PI * r, frac = total > 0 ? winning / total : 0;
  return (
    <svg width={44} height={44} viewBox="0 0 44 44">
      <circle cx="22" cy="22" r={r} fill="none" stroke="#a78bfa" strokeWidth={5} opacity={0.5} />
      <circle cx="22" cy="22" r={r} fill="none" stroke="#34d399" strokeWidth={5}
        strokeDasharray={`${(c * frac).toFixed(1)} ${c.toFixed(1)}`} strokeLinecap="round" transform="rotate(-90 22 22)" />
      <text x="22" y="26" textAnchor="middle" className="fill-white" style={{ fontSize: 13, fontWeight: 700 }}>{total}</text>
    </svg>
  );
}

function Card({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/5 bg-[#141419] p-4">
      <p className="truncate text-[11px] uppercase tracking-wider text-zinc-500">{label}</p>
      <div className="mt-2 flex items-end justify-between gap-2">{children}</div>
    </div>
  );
}

export function BottomStats() {
  const { botStatus, trades, dailyPnL } = useSupabase();
  const [tf, setTf] = useState<TF>('24H');

  const botState = botStatus?.bot_state ?? 'paused';
  const liveOn = botState === 'running';
  const liveDown = botState === 'error';

  const s = useMemo(() => {
    const closed = trades.filter((t) => t.status === 'closed');
    const open = trades.filter((t) => t.status === 'open');
    const winningOpen = open.filter((t) => Number(t.current_pnl ?? 0) > 0).length;

    // windowed (toggle) → win rate + P/L, calendar-day aligned
    const cutoff = windowCutoff(tf);
    const win = closed
      .filter((t) => new Date(t.closed_at ?? t.timestamp).getTime() >= cutoff)
      .sort((a, b) => new Date(a.closed_at ?? a.timestamp).getTime() - new Date(b.closed_at ?? b.timestamp).getTime());
    const wWins = win.filter((t) => Number(t.pnl ?? 0) > 0).length;
    const winRate = win.length ? (wWins / win.length) * 100 : 0;
    let rc = 0; const rolling = win.map((t, i) => { if (Number(t.pnl ?? 0) > 0) rc += 1; return (rc / (i + 1)) * 100; });
    let cum = 0; const pnlSpark = win.map((t) => (cum += Number(t.pnl ?? 0)));
    const pnlWin = cum;

    // today (local midnight) → W/L, trades, fees, last-10 squares
    const midnight = new Date(); midnight.setHours(0, 0, 0, 0);
    const todayT = closed
      .filter((t) => new Date(t.closed_at ?? t.timestamp).getTime() >= midnight.getTime())
      .sort((a, b) => new Date(b.closed_at ?? b.timestamp).getTime() - new Date(a.closed_at ?? a.timestamp).getTime());
    const tWins = todayT.filter((t) => Number(t.pnl ?? 0) > 0).length;
    const fees = todayT.reduce((sum, t) => sum + Number(t.entry_fee ?? 0) + Number(t.exit_fee ?? 0), 0);
    const last10 = todayT.slice(0, 10).reverse().map((t, i) => ({ key: t.id ?? i, pnl: Number(t.pnl ?? 0) }));

    // portfolio spark from daily cumulative
    let dc = 0; const deltaSpark: number[] = [];
    [...dailyPnL].forEach((d) => { dc += Number(d.daily_pnl ?? 0); deltaSpark.push(dc); });

    const delta = Number(botStatus?.delta_balance ?? botStatus?.capital ?? 0);
    const capital = Number(botStatus?.capital ?? delta);

    return {
      delta, deltaSpark: deltaSpark.length > 1 ? deltaSpark : [0, delta],
      openCount: open.length, winningOpen,
      winRate, rolling: rolling.length > 1 ? rolling : [winRate, winRate], winN: win.length,
      pnlWin, pnlSpark: pnlSpark.length > 1 ? pnlSpark : [0, pnlWin],
      capital,
      today: { wins: tWins, losses: todayT.length - tWins, total: todayT.length, fees, last10, pnl: todayT.reduce((x, t) => x + Number(t.pnl ?? 0), 0) },
    };
  }, [botStatus, trades, dailyPnL, tf]);

  const pnlUp = s.pnlWin >= 0;
  const capPct = s.capital > 0 ? `${pnlUp ? '+' : '−'}${Math.abs((s.pnlWin / s.capital) * 100).toFixed(2)}%` : '—';

  return (
    <div className="rounded-2xl border border-white/5 bg-[#101015] p-4">
      {/* header: live + timeframe toggle (left) · today detail (right) */}
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <span className={cn(
            'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold',
            liveDown ? 'bg-red-500/15 text-red-300' : liveOn ? 'bg-emerald-500/15 text-emerald-300' : 'bg-zinc-700/40 text-zinc-400',
          )}>
            <span className={cn('h-1.5 w-1.5 rounded-full', liveDown ? 'bg-red-400' : liveOn ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500')} />
            LIVE {liveDown ? 'DOWN' : liveOn ? 'ON' : 'OFF'}
          </span>
          <div className="flex gap-1">
            {(Object.keys(TF_DAYS) as TF[]).map((k) => (
              <button key={k} onClick={() => setTf(k)}
                className={cn('rounded px-2 py-0.5 text-[10px] font-semibold transition-colors',
                  tf === k ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300')}>
                {k}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]">
          <span className="text-zinc-500">Today</span>
          <span className={cn('font-mono font-semibold', s.today.pnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>
            {s.today.pnl >= 0 ? '+' : '−'}{formatCurrency(Math.abs(s.today.pnl))}
          </span>
          <span className="text-zinc-400 font-mono">{s.today.wins}W / {s.today.losses}L</span>
          <span className="text-zinc-400 font-mono">{s.today.total} trades</span>
          <span className="text-zinc-400 font-mono">fees ${s.today.fees.toFixed(2)}</span>
          <div className="flex gap-1">
            {Array.from({ length: 10 }).map((_, i) => {
              const slot = s.today.last10[i];
              return <span key={i} className={cn('h-3 w-3 rounded-sm', !slot ? 'bg-zinc-700/50' : slot.pnl > 0 ? 'bg-emerald-500' : slot.pnl < 0 ? 'bg-red-500' : 'bg-zinc-500')} />;
            })}
          </div>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-5">
        <Card label="Portfolio Value">
          <div>
            <div className="font-mono text-xl font-bold whitespace-nowrap text-white">{formatCurrency(s.delta)}</div>
            <p className="mt-0.5 text-[11px] text-emerald-400">Delta · live</p>
          </div>
          <Spark values={s.deltaSpark} color="#34d399" />
        </Card>

        <Card label="Open Positions">
          <div>
            <div className="font-mono text-xl font-bold whitespace-nowrap text-white">{s.openCount}</div>
            <p className="mt-0.5 text-[11px] text-zinc-400">{s.winningOpen} winning</p>
          </div>
          <Donut total={s.openCount} winning={s.winningOpen} />
        </Card>

        <Card label={`Win Rate (${tf})`}>
          <div>
            <div className="font-mono text-xl font-bold whitespace-nowrap text-white">{s.winRate.toFixed(0)}%</div>
            <p className="mt-0.5 text-[11px] text-zinc-400">{s.winN} trades</p>
          </div>
          <Spark values={s.rolling} color="#34d399" />
        </Card>

        <Card label={`Total P/L (${tf})`}>
          <div>
            <div className={cn('font-mono text-xl font-bold whitespace-nowrap', pnlUp ? 'text-emerald-400' : 'text-red-400')}>
              {pnlUp ? '+' : '−'}{formatCurrency(Math.abs(s.pnlWin))}
            </div>
            <p className={cn('mt-0.5 text-[11px]', pnlUp ? 'text-emerald-400' : 'text-red-400')}>{capPct}</p>
          </div>
          <Spark values={s.pnlSpark} color={pnlUp ? '#34d399' : '#f87171'} />
        </Card>

        <Card label="Capital">
          <div className="w-full">
            <div className="font-mono text-xl font-bold whitespace-nowrap text-white">{formatCurrency(s.capital)}</div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
              <div className="h-full rounded-full bg-sky-400" style={{ width: '100%' }} />
            </div>
            <p className="mt-1 text-[11px] text-zinc-500">deployed on Delta</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
