'use client';

import { useMemo, useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn, formatPnL } from '@/lib/utils';
import { PnLCalendar, buildDailyStats } from '@/components/dashboard/PnLCalendar';

export default function PnLPage() {
  const { filteredTrades } = useSupabase();

  // Default to current month (IST)
  const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  const dailyStats = useMemo(() => buildDailyStats(filteredTrades), [filteredTrades]);

  const monthLabel = new Date(year, month).toLocaleString('en-US', { month: 'long', year: 'numeric' });
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Monthly totals
  const monthStats = useMemo(() => {
    let totalPnl = 0;
    let totalFees = 0;
    let totalTrades = 0;
    let greenDays = 0;
    let redDays = 0;

    for (let d = 1; d <= daysInMonth; d++) {
      const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const entry = dailyStats.get(dateKey);
      if (entry) {
        totalPnl += entry.pnl;
        totalFees += entry.fees;
        totalTrades += entry.trades;
        if (entry.pnl > 0) greenDays++;
        else if (entry.pnl < 0) redDays++;
      }
    }
    return { totalPnl, totalFees, totalTrades, greenDays, redDays };
  }, [dailyStats, year, month, daysInMonth]);

  const prevMonth = () => {
    if (month === 0) { setYear(y => y - 1); setMonth(11); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setYear(y => y + 1); setMonth(0); }
    else setMonth(m => m + 1);
  };

  const pnlColor = (v: number) => v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-zinc-500';

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold tracking-tight text-white">P&L Calendar</h1>

      {/* Month navigation */}
      <div className="flex items-center justify-between">
        <button onClick={prevMonth} className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors">
          <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
        </button>
        <span className="text-sm font-semibold text-white tracking-wide">{monthLabel}</span>
        <button onClick={nextMonth} className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors">
          <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" /></svg>
        </button>
      </div>

      {/* Monthly summary */}
      <div className="grid grid-cols-4 gap-2 text-center">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Net P&L</div>
          <div className={cn('text-sm font-mono font-semibold', pnlColor(monthStats.totalPnl))}>
            {formatPnL(monthStats.totalPnl)}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Fees</div>
          <div className="text-sm font-mono font-semibold text-zinc-300">
            ${monthStats.totalFees.toFixed(2)}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Trades</div>
          <div className="text-sm font-mono font-semibold text-white">
            {monthStats.totalTrades}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Days</div>
          <div className="text-sm font-mono font-semibold">
            <span className="text-emerald-400">{monthStats.greenDays}</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className="text-red-400">{monthStats.redDays}</span>
          </div>
        </div>
      </div>

      {/* Calendar */}
      <PnLCalendar dailyStats={dailyStats} year={year} month={month} />

      {/* Legend */}
      <div className="flex items-center justify-center gap-1 text-[10px] text-zinc-500">
        <span>Loss</span>
        <div className="flex gap-0.5">
          <div className="w-3 h-3 rounded-sm bg-red-500" />
          <div className="w-3 h-3 rounded-sm bg-red-500/70" />
          <div className="w-3 h-3 rounded-sm bg-red-600/50" />
          <div className="w-3 h-3 rounded-sm bg-zinc-800/40" />
          <div className="w-3 h-3 rounded-sm bg-emerald-600/50" />
          <div className="w-3 h-3 rounded-sm bg-emerald-500/70" />
          <div className="w-3 h-3 rounded-sm bg-emerald-500" />
        </div>
        <span>Profit</span>
      </div>
    </div>
  );
}
