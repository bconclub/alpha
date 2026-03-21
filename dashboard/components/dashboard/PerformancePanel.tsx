'use client';

import { useMemo, useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import {
  formatCurrency,
  formatPnL,
  formatPercentage,
  cn,
} from '@/lib/utils';
import type { DailyPnL } from '@/lib/types';

/** Build a calendar grid for a given month: 7 columns (Mon–Sun), ~5 rows */
function buildMonthGrid(year: number, month: number) {
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  // Monday = 0 ... Sunday = 6
  const startDay = (first.getDay() + 6) % 7;
  const totalDays = last.getDate();
  const weeks: (number | null)[][] = [];
  let week: (number | null)[] = new Array(startDay).fill(null);
  for (let d = 1; d <= totalDays; d++) {
    week.push(d);
    if (week.length === 7) {
      weeks.push(week);
      week = [];
    }
  }
  if (week.length > 0) {
    while (week.length < 7) week.push(null);
    weeks.push(week);
  }
  return weeks;
}

function getDayColor(pnl: number, maxAbs: number): string {
  if (maxAbs === 0) return 'bg-zinc-800/40';
  const intensity = Math.min(Math.abs(pnl) / maxAbs, 1);
  if (pnl > 0) {
    if (intensity > 0.7) return 'bg-[#00c853] text-black';
    if (intensity > 0.3) return 'bg-[#00c853]/60 text-white';
    return 'bg-[#00c853]/25 text-white';
  } else {
    if (intensity > 0.7) return 'bg-[#ff1744] text-white';
    if (intensity > 0.3) return 'bg-[#ff1744]/60 text-white';
    return 'bg-[#ff1744]/25 text-white';
  }
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

export function PerformancePanel() {
  const { dailyPnL, trades, pnlByExchange } = useSupabase();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [hoveredDay, setHoveredDay] = useState<{ date: string; pnl: DailyPnL; x: number; y: number } | null>(null);

  // Build lookup map: "YYYY-MM-DD" -> DailyPnL
  const pnlMap = useMemo(() => {
    const map = new Map<string, DailyPnL>();
    for (const d of dailyPnL) {
      const key = d.trade_date.slice(0, 10);
      map.set(key, d);
    }
    return map;
  }, [dailyPnL]);

  // Figure out which months to show (all months with data, or last 3 months)
  const months = useMemo(() => {
    if (dailyPnL.length === 0) {
      const now = new Date();
      return [{ year: now.getFullYear(), month: now.getMonth() }];
    }
    const dates = dailyPnL.map((d) => new Date(d.trade_date));
    const minDate = new Date(Math.min(...dates.map((d) => d.getTime())));
    const maxDate = new Date(Math.max(...dates.map((d) => d.getTime())));
    const result: { year: number; month: number }[] = [];
    let y = minDate.getFullYear();
    let m = minDate.getMonth();
    while (y < maxDate.getFullYear() || (y === maxDate.getFullYear() && m <= maxDate.getMonth())) {
      result.push({ year: y, month: m });
      m++;
      if (m > 11) { m = 0; y++; }
    }
    return result;
  }, [dailyPnL]);

  // Max absolute P&L for color scaling
  const maxAbsPnL = useMemo(() => {
    let max = 0;
    for (const d of dailyPnL) {
      max = Math.max(max, Math.abs(d.daily_pnl));
    }
    return max;
  }, [dailyPnL]);

  // Stats
  const totalWins = trades.filter((t) => t.pnl > 0).length;
  const totalTrades = trades.filter((t) => t.status === 'closed').length;
  const winRate = totalTrades > 0 ? (totalWins / totalTrades) * 100 : 0;
  const totalPnL = trades.reduce((s, t) => s + t.pnl, 0);

  const { grossPnL, totalFees } = useMemo(() => {
    let gross = 0;
    let fees = 0;
    for (const t of trades) {
      const tradeFees = (t.entry_fee ?? 0) + (t.exit_fee ?? 0);
      fees += tradeFees;
      gross += t.gross_pnl != null ? t.gross_pnl : (t.pnl + tradeFees);
    }
    return { grossPnL: gross, totalFees: fees };
  }, [trades]);

  // Winning / losing day counts
  const { winDays, lossDays } = useMemo(() => {
    let w = 0, l = 0;
    for (const d of dailyPnL) {
      if (d.daily_pnl > 0) w++;
      else if (d.daily_pnl < 0) l++;
    }
    return { winDays: w, lossDays: l };
  }, [dailyPnL]);

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="w-full flex items-center justify-between p-4 md:p-5 hover:bg-zinc-800/20 transition-colors"
      >
        <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider">
          Performance
        </h3>
        <div className="flex items-center gap-3 md:gap-4">
          <div className="flex flex-wrap gap-2 md:gap-3 text-xs">
            <span className={cn('font-mono font-bold', totalPnL >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
              {formatPnL(totalPnL)} net
            </span>
            <span className="text-zinc-500">|</span>
            <span className="text-zinc-300">{formatPercentage(winRate)} WR</span>
            <span className="text-zinc-500">|</span>
            <span className="text-zinc-400">{totalTrades} trades</span>
          </div>
          <svg
            className={cn('w-4 h-4 text-zinc-500 transition-transform', isCollapsed ? '' : 'rotate-180')}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {!isCollapsed && (
        <div className="px-3 pb-4 md:px-5 md:pb-5 space-y-4">
          {/* P&L breakdown — big numbers */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-lg px-4 py-3">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Net P&L</div>
              <div className={cn('text-xl font-mono font-bold', totalPnL >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
                {formatPnL(totalPnL)}
              </div>
            </div>
            <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-lg px-4 py-3">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Gross P&L</div>
              <div className={cn('text-xl font-mono font-bold', grossPnL >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
                {formatPnL(grossPnL)}
              </div>
            </div>
            <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-lg px-4 py-3">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Total Fees</div>
              <div className="text-xl font-mono font-bold text-zinc-300">
                ${totalFees.toFixed(2)}
              </div>
              {totalTrades > 0 && (
                <div className="text-[10px] font-mono text-zinc-600 mt-0.5">
                  ${(totalFees / totalTrades).toFixed(4)}/trade
                </div>
              )}
            </div>
            <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-lg px-4 py-3">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Win Rate</div>
              <div className="text-xl font-mono font-bold text-zinc-100">
                {winRate.toFixed(1)}%
              </div>
              <div className="text-[10px] text-zinc-600 mt-0.5">
                {totalWins}W / {totalTrades - totalWins}L
              </div>
            </div>
          </div>

          {/* Calendar heatmap */}
          <div className="relative">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[10px] text-zinc-500 uppercase tracking-wider">Daily P&L Calendar</h4>
              <div className="flex items-center gap-1.5 text-[10px] text-zinc-600">
                <span className="text-[#ff1744]">{lossDays}d loss</span>
                <span>/</span>
                <span className="text-[#00c853]">{winDays}d profit</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {months.map(({ year, month }) => {
                const weeks = buildMonthGrid(year, month);
                return (
                  <div key={`${year}-${month}`} className="min-w-0">
                    <div className="text-[11px] text-zinc-400 font-medium mb-1.5">
                      {MONTH_NAMES[month]} {year}
                    </div>
                    {/* Day labels */}
                    <div className="grid grid-cols-7 gap-[2px] mb-[2px]">
                      {DAY_LABELS.map((label, i) => (
                        <div key={i} className="text-[9px] text-zinc-600 text-center">{label}</div>
                      ))}
                    </div>
                    {/* Weeks */}
                    {weeks.map((week, wi) => (
                      <div key={wi} className="grid grid-cols-7 gap-[2px] mb-[2px]">
                        {week.map((day, di) => {
                          if (day === null) {
                            return <div key={di} className="aspect-square rounded-sm" />;
                          }
                          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                          const dayData = pnlMap.get(dateStr);
                          const hasTrade = !!dayData;
                          const pnl = dayData?.daily_pnl ?? 0;

                          return (
                            <div
                              key={di}
                              className={cn(
                                'aspect-square rounded-sm flex items-center justify-center text-[9px] font-mono cursor-default transition-all',
                                hasTrade
                                  ? getDayColor(pnl, maxAbsPnL)
                                  : 'bg-zinc-800/20 text-zinc-700',
                              )}
                              onMouseEnter={(e) => {
                                if (dayData) {
                                  const rect = e.currentTarget.getBoundingClientRect();
                                  setHoveredDay({ date: dateStr, pnl: dayData, x: rect.left, y: rect.bottom });
                                }
                              }}
                              onMouseLeave={() => setHoveredDay(null)}
                            >
                              {day}
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>

            {/* Tooltip */}
            {hoveredDay && (
              <div
                className="fixed z-50 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs pointer-events-none shadow-xl"
                style={{ left: hoveredDay.x, top: hoveredDay.y + 4 }}
              >
                <p className="text-zinc-400 mb-1">{hoveredDay.date}</p>
                <p className={hoveredDay.pnl.daily_pnl >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]'}>
                  Total: {formatCurrency(hoveredDay.pnl.daily_pnl)}
                </p>
                <p className="text-[#2196f3]">Spot: {formatCurrency(hoveredDay.pnl.spot_pnl)}</p>
                <p className="text-[#ffd600]">Futures: {formatCurrency(hoveredDay.pnl.futures_pnl)}</p>
              </div>
            )}
          </div>

          {/* Compact bottom stats */}
          <div className="flex flex-wrap gap-3 text-xs">
            {pnlByExchange.map((ex) => (
              <div key={ex.exchange} className="flex items-center gap-1.5 bg-zinc-900/40 border border-zinc-800/50 rounded px-2.5 py-1.5">
                <span className="text-zinc-400 capitalize">{ex.exchange}</span>
                <span className={cn('font-mono', ex.total_pnl >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
                  {formatPnL(ex.total_pnl)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
