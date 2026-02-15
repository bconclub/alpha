'use client';

import { useEffect, useState, useMemo } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { formatCurrency, formatPnL, formatTimeAgo, cn } from '@/lib/utils';

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function ISTClock() {
  const [time, setTime] = useState('');

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      // Format time in IST (UTC+5:30) using Intl
      const istStr = now.toLocaleTimeString('en-GB', {
        timeZone: 'Asia/Kolkata',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      setTime(istStr + ' IST');
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="font-mono text-xs text-zinc-400">{time}</span>
  );
}

export function LiveStatusBar() {
  const { botStatus, isConnected, pnlByExchange, trades } = useSupabase();

  const binanceConnected = botStatus?.binance_connected || (Number(botStatus?.binance_balance ?? 0) > 0) || isConnected;
  const deltaConnected = botStatus?.delta_connected || (Number(botStatus?.delta_balance ?? 0) > 0) || isConnected;
  const botState = botStatus?.bot_state ?? (isConnected ? 'running' : 'paused');

  // Use per-exchange P&L view data as fallback for balances
  const binancePnl = pnlByExchange.find((e) => e.exchange === 'binance');
  const deltaPnl = pnlByExchange.find((e) => e.exchange === 'delta');

  const binanceBalance = Number(botStatus?.binance_balance ?? 0);
  const deltaBalance = Number(botStatus?.delta_balance ?? 0);
  const deltaBalanceInr = botStatus?.delta_balance_inr;

  // Total capital: sum of actual exchange balances (fall back to config 'capital' field)
  const hasFreshBalance = binanceBalance > 0 || deltaBalance > 0;
  const totalCapital = hasFreshBalance ? (binanceBalance + deltaBalance) : (botStatus?.capital || 0);

  // Open positions count for display
  const openPositionCount = botStatus?.open_positions ?? 0;

  const shortingEnabled = botStatus?.shorting_enabled ?? false;
  const leverageLevel = botStatus?.leverage ?? botStatus?.leverage_level ?? 1;
  const activeStrategiesCount = botStatus?.active_strategy_count ?? botStatus?.active_strategies_count ?? 0;
  const uptimeSeconds = botStatus?.uptime_seconds ?? 0;

  // Total P&L from bot status
  const totalPnL = botStatus?.total_pnl ?? 0;
  const winRate = botStatus?.win_rate ?? 0;

  // P&L stats by time range — 24h, 7D, 14D, 30D
  const [pnlRange, setPnlRange] = useState<'24h' | '7d' | '14d' | '30d'>('24h');

  const pnlStats = useMemo(() => {
    const now = Date.now();
    const istOffsetMs = 5.5 * 60 * 60 * 1000;

    // For 24h: start of today IST. For 7/14/30D: N days ago from now.
    let cutoffMs: number;
    if (pnlRange === '24h') {
      const istNow = new Date(now + istOffsetMs);
      const todayIST = istNow.toISOString().slice(0, 10);
      cutoffMs = new Date(todayIST + 'T00:00:00+05:30').getTime();
    } else {
      const days = pnlRange === '7d' ? 7 : pnlRange === '14d' ? 14 : 30;
      cutoffMs = now - days * 24 * 60 * 60 * 1000;
    }

    let pnl = 0;
    let total = 0;
    let wins = 0;
    for (const t of trades) {
      if (t.status !== 'closed') continue;
      const tradeTime = new Date(t.timestamp).getTime();
      if (tradeTime >= cutoffMs) {
        pnl += t.pnl ?? 0;
        total++;
        if ((t.pnl ?? 0) > 0) wins++;
      }
    }
    const winRate = total > 0 ? (wins / total) * 100 : 0;
    return { pnl, total, wins, losses: total - wins, winRate };
  }, [trades, pnlRange]);

  // Count active strategies from trades if not provided
  const derivedStrategyCount = useMemo(() => {
    if (activeStrategiesCount > 0) return activeStrategiesCount;
    const strategies = new Set(trades.filter((t) => t.status === 'open').map((t) => t.strategy));
    return strategies.size || 1;
  }, [activeStrategiesCount, trades]);

  // Heartbeat freshness — bot saves status every 5 minutes,
  // so allow up to 7 min before marking stale (5 min interval + network/clock drift)
  const lastHeartbeat = botStatus?.timestamp;
  const isStale = useMemo(() => {
    if (!lastHeartbeat) return true;
    return Date.now() - new Date(lastHeartbeat).getTime() > 420_000; // 7 minutes
  }, [lastHeartbeat]);

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Exchange Cards */}
        <div className="flex flex-col sm:flex-row gap-3 flex-1 min-w-0">
          {/* Binance Card */}
          <div className="flex-1 bg-zinc-900/50 border border-zinc-800 rounded-lg px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={cn(
                  'w-2 h-2 rounded-full',
                  binanceConnected && !isStale ? 'bg-[#00c853] animate-pulse' : 'bg-red-500',
                )}
              />
              <span className="text-sm font-semibold text-[#f0b90b]">BINANCE</span>
              <span className="text-[10px] text-zinc-500">(Spot)</span>
            </div>
            {binanceBalance > 0 ? (
              <div className="flex items-baseline gap-2 min-w-0">
                <span className="font-mono text-base md:text-lg text-white truncate">{formatCurrency(binanceBalance)}</span>
              </div>
            ) : binancePnl ? (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-zinc-500">P&L:</span>
                <span className={cn('font-mono', binancePnl.total_pnl >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
                  {formatPnL(binancePnl.total_pnl)}
                </span>
              </div>
            ) : (
              <span className="text-xs text-zinc-500">No data</span>
            )}
          </div>

          {/* Delta Card */}
          <div className="flex-1 bg-zinc-900/50 border border-zinc-800 rounded-lg px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={cn(
                  'w-2 h-2 rounded-full',
                  deltaConnected && !isStale ? 'bg-[#00c853] animate-pulse' : 'bg-red-500',
                )}
              />
              <span className="text-sm font-semibold text-[#00d2ff]">DELTA</span>
              <span className="text-[10px] text-zinc-500">(Futures)</span>
            </div>
            {deltaBalance > 0 ? (
              <div className="flex items-baseline gap-2 min-w-0 flex-wrap">
                <span className="font-mono text-base md:text-lg text-white truncate">{formatCurrency(deltaBalance)}</span>
                {deltaBalanceInr != null && (
                  <span className="text-[10px] text-zinc-500 shrink-0">~{deltaBalanceInr.toLocaleString()}</span>
                )}
              </div>
            ) : deltaPnl ? (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-zinc-500">P&L:</span>
                <span className={cn('font-mono', deltaPnl.total_pnl >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
                  {formatPnL(deltaPnl.total_pnl)}
                </span>
              </div>
            ) : (
              <span className="text-xs text-zinc-500">No data</span>
            )}
          </div>

          {/* P&L Summary Card — switchable time range */}
          <div className="flex-1 bg-zinc-900/50 border border-zinc-800 rounded-lg px-4 py-3">
            <div className="flex items-center gap-1.5 mb-1">
              {(['24h', '7d', '14d', '30d'] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => setPnlRange(range)}
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors',
                    pnlRange === range
                      ? 'bg-zinc-700 text-white'
                      : 'text-zinc-500 hover:text-zinc-300',
                  )}
                >
                  {range.toUpperCase()}
                </button>
              ))}
            </div>
            {pnlStats.total > 0 ? (
              <>
                <div className="flex items-baseline gap-2">
                  <span className={cn(
                    'font-mono text-base md:text-lg font-bold',
                    pnlStats.pnl >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]',
                  )}>
                    {pnlStats.pnl >= 0 ? '+' : ''}{formatCurrency(pnlStats.pnl)}
                  </span>
                </div>
                <div className="text-[10px] text-zinc-500 font-mono">
                  {pnlStats.wins}W / {pnlStats.losses}L · {pnlStats.winRate.toFixed(0)}% WR · {pnlStats.total} trades
                </div>
              </>
            ) : (
              <span className="text-xs text-zinc-500">No trades</span>
            )}
          </div>
        </div>

        {/* Center: Total Capital + Bot State */}
        <div className="flex flex-col items-center gap-1 border-y md:border-y-0 md:border-x border-zinc-800 py-3 md:py-0 md:px-6">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500">Total Capital</span>
          <span className="font-mono text-base md:text-xl font-bold text-white truncate max-w-full">
            {formatCurrency(totalCapital)}
          </span>
          {hasFreshBalance && (
            <div className="flex items-center gap-3 text-[10px] font-mono text-zinc-400">
              {openPositionCount > 0 && (
                <span className="text-amber-400">{openPositionCount} open</span>
              )}
            </div>
          )}
          <div className="flex items-center gap-3 mt-1">
            <span
              className={cn(
                'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium',
                botState === 'running'
                  ? 'bg-[#00c853]/10 text-[#00c853]'
                  : 'bg-[#ffd600]/10 text-[#ffd600]',
              )}
            >
              <span
                className={cn(
                  'w-1.5 h-1.5 rounded-full',
                  botState === 'running' ? 'bg-[#00c853]' : 'bg-[#ffd600]',
                )}
              />
              {botState === 'running' ? 'Running' : 'Paused'}
            </span>
            {uptimeSeconds > 0 && (
              <span className="text-[10px] text-zinc-500">{formatUptime(uptimeSeconds)}</span>
            )}
          </div>
        </div>

        {/* Right: Indicators + Clock */}
        <div className="flex items-center justify-between sm:justify-start gap-4">
          <div className="flex flex-col gap-1.5 text-[10px]">
            <div className="flex items-center gap-2">
              <span className="text-zinc-500">Shorting</span>
              <span className={shortingEnabled ? 'text-[#00c853]' : 'text-zinc-600'}>
                {shortingEnabled ? 'ON' : 'OFF'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-zinc-500">Leverage</span>
              <span className="text-[#ffd600] font-mono">{leverageLevel}x</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-zinc-500">Strategies</span>
              <span className="text-[#2196f3] font-mono">{derivedStrategyCount}</span>
            </div>
          </div>
          <div className="border-l border-zinc-800 pl-4 flex flex-col items-end gap-1">
            <ISTClock />
            <span className="text-[9px] text-zinc-600 font-mono">
              v{process.env.APP_VERSION ?? '?'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
