'use client';

import { useMemo, useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import {
  formatPnL,
  formatPercentage,
  cn,
} from '@/lib/utils';
import { PnLCalendar, buildDailyStats } from './PnLCalendar';

export function PerformancePanel() {
  const { trades, pnlByExchange } = useSupabase();
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Current month in IST
  const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  const monthLabel = new Date(year, month).toLocaleString('en-US', { month: 'long', year: 'numeric' });

  const dailyStats = useMemo(() => buildDailyStats(trades), [trades]);

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

  // Win/loss days from the stats map
  const { winDays, lossDays } = useMemo(() => {
    let w = 0, l = 0;
    for (const [, s] of dailyStats) {
      if (s.pnl > 0) w++;
      else if (s.pnl < 0) l++;
    }
    return { winDays: w, lossDays: l };
  }, [dailyStats]);

  const prevMonth = () => {
    if (month === 0) { setYear(y => y - 1); setMonth(11); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setYear(y => y + 1); setMonth(0); }
    else setMonth(m => m + 1);
  };

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

          {/* Calendar heatmap — single month with nav */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[10px] text-zinc-500 uppercase tracking-wider">Daily P&L Calendar</h4>
              <div className="flex items-center gap-1.5 text-[10px] text-zinc-600">
                <span className="text-[#ff1744]">{lossDays}d loss</span>
                <span>/</span>
                <span className="text-[#00c853]">{winDays}d profit</span>
              </div>
            </div>

            {/* Month nav */}
            <div className="flex items-center justify-between mb-2">
              <button onClick={prevMonth} className="p-1 rounded text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors">
                <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
              </button>
              <span className="text-xs font-medium text-zinc-400">{monthLabel}</span>
              <button onClick={nextMonth} className="p-1 rounded text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors">
                <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" /></svg>
              </button>
            </div>

            <div className="max-w-lg">
              <PnLCalendar dailyStats={dailyStats} year={year} month={month} />
            </div>
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
