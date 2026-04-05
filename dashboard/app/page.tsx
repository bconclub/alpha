'use client';

import { useState, useMemo, useEffect } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { formatCurrency, formatNumber, cn } from '@/lib/utils';
import { MarketOverview } from '@/components/dashboard/MarketOverview';
import { BBSqueezePanel } from '@/components/dashboard/BBSqueezePanel';
import { LivePositions } from '@/components/dashboard/LivePositions';
import { PerformancePanel } from '@/components/dashboard/PerformancePanel';

// IST Clock component
function ISTClock() {
  const [time, setTime] = useState('');

  useEffect(() => {
    const tick = () => {
      const now = new Date();
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

  return <span className="font-mono text-xs text-zinc-500">{time}</span>;
}

// Mini sparkline for P&L chart
function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null;

  const width = 100;
  const height = 80;
  const padding = 2;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = padding + (i / (data.length - 1)) * (width - padding * 2);
    const y = padding + (1 - (v - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  const firstX = padding;
  const lastX = padding + ((data.length - 1) / (data.length - 1)) * (width - padding * 2);
  const areaPoints = `${firstX},${height} ${points.join(' ')} ${lastX},${height}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="shrink-0">
      <defs>
        <linearGradient id={`spark-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={areaPoints} fill={`url(#spark-${color.replace('#', '')})`} />
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function DashboardPage() {
  const { botStatus, isConnected, trades, dailyPnL } = useSupabase();
  
  const [pnlRange, setPnlRange] = useState<'24h' | '7d' | '14d' | '30d'>('24h');

  // Bot state
  const botState = botStatus?.bot_state ?? (isConnected ? 'running' : 'paused');
  const uptimeSeconds = botStatus?.uptime_seconds ?? 0;
  
  // Market regime
  const regime = botStatus?.market_regime ?? 'SIDEWAYS';
  const chopScore = botStatus?.chop_score ?? 0;
  const atrRatio = botStatus?.atr_ratio ?? 1;
  const netChange = botStatus?.net_change_30m ?? 0;
  const regimeSince = botStatus?.regime_since;

  const regimeConfig: Record<string, { label: string; icon: string; color: string }> = {
    TRENDING_UP:   { label: 'TRENDING UP',   icon: '↗', color: 'text-emerald-400' },
    TRENDING_DOWN: { label: 'TRENDING DOWN', icon: '↘', color: 'text-red-400' },
    SIDEWAYS:      { label: 'SIDEWAYS',      icon: '↔', color: 'text-amber-400' },
    CHOPPY:        { label: 'CHOPPY',        icon: '⚡', color: 'text-red-400' },
  };
  const rc = regimeConfig[regime] ?? regimeConfig.SIDEWAYS;

  const regimeDuration = useMemo(() => {
    if (!regimeSince) return '';
    const elapsed = Math.max(0, Math.floor((Date.now() - new Date(regimeSince).getTime()) / 1000));
    if (elapsed < 60) return `${elapsed}s`;
    if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m`;
    return `${Math.floor(elapsed / 3600)}h ${Math.floor((elapsed % 3600) / 60)}m`;
  }, [regimeSince]);

  // Delta balance
  const deltaBalance = Number(botStatus?.delta_balance ?? 0);
  const inrRate = botStatus?.inr_usd_rate ?? 86.5;
  const totalCapital = deltaBalance > 0 ? deltaBalance : (botStatus?.capital || 0);
  const capitalInr = Math.round(totalCapital * inrRate);

  // P&L stats
  const pnlStats = useMemo(() => {
    const now = Date.now();
    const istOffsetMs = 5.5 * 60 * 60 * 1000;

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
    let fees = 0;
    let grossPnl = 0;
    
    for (const t of trades) {
      if (t.status !== 'closed') continue;
      const tradeTime = new Date(t.timestamp).getTime();
      if (tradeTime >= cutoffMs) {
        pnl += t.pnl ?? 0;
        total++;
        if ((t.pnl ?? 0) > 0) wins++;
        const tradeFees = (t.entry_fee ?? 0) + (t.exit_fee ?? 0);
        fees += tradeFees;
        grossPnl += t.gross_pnl != null ? t.gross_pnl : ((t.pnl ?? 0) + tradeFees);
      }
    }
    
    const winRate = total > 0 ? (wins / total) * 100 : 0;
    return { pnl, total, wins, losses: total - wins, winRate, fees, grossPnl };
  }, [trades, pnlRange]);

  // Sparkline data
  const sparklineData = useMemo(() => {
    const now = Date.now();
    const days = pnlRange === '24h' ? 1 : pnlRange === '7d' ? 7 : pnlRange === '14d' ? 14 : 30;
    const cutoffMs = now - days * 24 * 60 * 60 * 1000;

    const filtered = dailyPnL
      .filter((d) => new Date(d.trade_date).getTime() >= cutoffMs)
      .sort((a, b) => a.trade_date.localeCompare(b.trade_date));

    if (filtered.length === 0) return [];

    let cumulative = 0;
    return filtered.map((d) => {
      cumulative += d.daily_pnl;
      return cumulative;
    });
  }, [dailyPnL, pnlRange]);

  const sparkColor = pnlStats.pnl >= 0 ? '#00c853' : '#ff1744';

  // Format uptime
  const formatUptime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  // Total trades count
  const totalTrades = trades.filter(t => t.status === 'closed').length;
  const liveStrategyCount = useMemo(() => {
    const strategies = new Set(trades.map((t) => t.strategy));
    return strategies.size || 1;
  }, [trades]);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 md:p-6">
      {/* TOP ROW — Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {/* Delta Balance Card */}
        <div className="bg-[#141419] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className={cn(
              'w-2 h-2 rounded-full',
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            )} />
            <span className="text-xs uppercase tracking-wider text-gray-400">Delta</span>
          </div>
          <div className="text-2xl font-bold font-mono">{formatCurrency(deltaBalance)}</div>
          <div className="text-xs text-gray-500 mt-1">
            {pnlStats.wins}W / {pnlStats.losses}L • {pnlStats.winRate.toFixed(0)}% WR • {pnlStats.total} trades
          </div>
          <div className="text-xs mt-1">
            <span className={pnlStats.grossPnl >= 0 ? 'text-green-400' : 'text-red-400'}>
              {pnlStats.grossPnl >= 0 ? '+' : ''}{formatCurrency(pnlStats.grossPnl)} P&L
            </span>
            <span className="text-gray-600"> • </span>
            <span className="text-gray-500">${pnlStats.fees.toFixed(2)} fees</span>
          </div>
        </div>

        {/* P&L Chart Card */}
        <div className="bg-[#141419] border border-white/5 rounded-xl p-4 md:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div className="flex gap-2">
              {(['24h', '7d', '14d', '30d'] as const).map((period) => (
                <button 
                  key={period}
                  onClick={() => setPnlRange(period)}
                  className={cn(
                    'px-3 py-1 text-xs rounded transition-colors',
                    pnlRange === period ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-gray-300'
                  )}
                >
                  {period.toUpperCase()}
                </button>
              ))}
            </div>
            <span className="text-xs text-gray-500">P&L</span>
          </div>
          
          <div className="flex items-end gap-4">
            <div className="flex-1">
              {sparklineData.length > 0 ? (
                <MiniSparkline data={sparklineData} color={sparkColor} />
              ) : (
                <div className="h-20 bg-gray-800/30 rounded flex items-center justify-center">
                  <span className="text-xs text-gray-600">No data</span>
                </div>
              )}
            </div>
          </div>
          
          <div className="flex justify-between mt-2">
            <span className={cn(
              'text-xs',
              pnlStats.pnl >= 0 ? 'text-green-400' : 'text-red-400'
            )}>
              {pnlStats.pnl >= 0 ? '+' : ''}{formatCurrency(pnlStats.pnl)} {pnlStats.total > 0 ? Math.round((pnlStats.pnl / Math.abs(totalCapital || 1)) * 100) : 0}%
            </span>
            <span className="text-xs text-gray-500">
              {pnlStats.wins}W / {pnlStats.losses}L • {pnlStats.winRate.toFixed(0)}% WR • {pnlStats.total} trades
            </span>
          </div>
        </div>

        {/* Market Regime Card */}
        <div className="bg-[#141419] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className={cn('text-lg', rc.color)}>{rc.icon}</span>
            <span className={cn('text-sm font-bold', rc.color)}>{rc.label}</span>
          </div>
          <div className="text-xs text-gray-400 space-y-1">
            <div className="flex justify-between">
              <span>Chop:</span>
              <span className="font-mono">{chopScore.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>ATR:</span>
              <span className="font-mono">{atrRatio.toFixed(1)}x</span>
            </div>
            <div className="flex justify-between">
              <span>Net:</span>
              <span className={netChange >= 0 ? 'text-green-400' : 'text-red-400'}>
                {netChange >= 0 ? '+' : ''}{netChange.toFixed(2)}%
              </span>
            </div>
            {regimeDuration && (
              <div className="flex justify-between text-gray-500">
                <span>Since</span>
                <span>{regimeDuration}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* SECOND ROW — Total Capital & Status */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 px-2 gap-4">
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wider">Total Capital</div>
          <div className="text-2xl font-bold">
            {formatCurrency(totalCapital)}
            {capitalInr > 0 && (
              <span className="text-sm text-gray-500 ml-2">₹{capitalInr.toLocaleString('en-IN')}</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={cn(
              'w-2 h-2 rounded-full',
              botState === 'running' ? 'bg-green-500' : 'bg-yellow-500'
            )} />
            <span className={cn(
              'text-xs',
              botState === 'running' ? 'text-green-500' : 'text-yellow-500'
            )}>
              {botState === 'running' ? 'Running' : 'Paused'}
            </span>
            {uptimeSeconds > 0 && (
              <span className="text-xs text-gray-500">{formatUptime(uptimeSeconds)}</span>
            )}
          </div>
        </div>
        
        <div className="text-right">
          <div className="text-xs text-gray-500">Strategies: <span className="text-blue-400 font-mono">{liveStrategyCount}</span></div>
          <div className="text-xs text-gray-500">Total Trades: <span className="text-gray-300 font-mono">{totalTrades}</span></div>
          <div className="text-xs text-gray-600">Alpha v{process.env.ALPHA_VERSION ?? '0.12.2'}</div>
          <ISTClock />
        </div>
      </div>

      {/* Live Positions (if any) */}
      <LivePositions />

      {/* THIRD ROW — Market Overview + BB Squeeze */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <MarketOverview />
        <BBSqueezePanel />
      </div>

      {/* Performance Panel */}
      <div className="mt-6">
        <PerformancePanel />
      </div>
    </div>
  );
}
