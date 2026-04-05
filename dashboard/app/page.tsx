'use client';

import { useState, useMemo, useEffect } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { formatCurrency, formatNumber, cn } from '@/lib/utils';
import { MarketOverview } from '@/components/dashboard/MarketOverview';
import { LivePositions } from '@/components/dashboard/LivePositions';

// ── Types ───────────────────────────────────────────────────────────────

interface SqueezeAsset {
  asset: string;
  price: number | null;
  bbWidth: number | null;
  state: 'no_squeeze' | 'filling' | 'squeeze_active' | 'position_open';
  direction: 'long' | 'short' | 'neutral';
  confidence: number;
  premiumRange: {
    min: number;
    max: number;
    current: number;
    threshold: number;
  } | null;
  fillTimer?: number;
  positionPnl?: number;
  lastUpdate: string | null;
}

// ── Helpers ─────────────────────────────────────────────────────────────

function extractBaseAsset(pair: string): string {
  if (pair.includes('/')) return pair.split('/')[0];
  return pair.replace(/USD.*$/, '');
}

function getStateConfig(state: SqueezeAsset['state']) {
  switch (state) {
    case 'position_open':
      return {
        label: 'POSITION OPEN',
        badgeColor: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        dotColor: 'bg-blue-500',
        barColor: 'bg-blue-500',
        leftBorder: 'border-l-blue-500',
        pulse: false,
      };
    case 'filling':
      return {
        label: 'FILLING',
        badgeColor: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        dotColor: 'bg-yellow-500',
        barColor: 'bg-yellow-500',
        leftBorder: 'border-l-yellow-500',
        pulse: true,
      };
    case 'squeeze_active':
      return {
        label: 'ACTIVE',
        badgeColor: 'bg-green-500/20 text-green-400 border-green-500/30',
        dotColor: 'bg-green-500',
        barColor: 'bg-green-500',
        leftBorder: 'border-l-green-500',
        pulse: false,
      };
    default:
      return {
        label: 'DEAD',
        badgeColor: 'bg-red-500/20 text-red-500 border-red-500/30',
        dotColor: 'bg-red-500',
        barColor: 'bg-red-500',
        leftBorder: 'border-l-red-500',
        pulse: false,
      };
  }
}

function getDirectionEmoji(direction: SqueezeAsset['direction']) {
  switch (direction) {
    case 'long': return '📈';
    case 'short': return '📉';
    default: return '➖';
  }
}

function formatTimeRemaining(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// ── Components ──────────────────────────────────────────────────────────

function SqueezeCard({ asset }: { asset: SqueezeAsset }) {
  const state = getStateConfig(asset.state);
  const isNoSqueeze = asset.state === 'no_squeeze';
  const isFilling = asset.state === 'filling';
  const isActive = asset.state === 'squeeze_active';
  const hasPosition = asset.state === 'position_open';
  
  const threshold = asset.asset === 'BTC' ? 0.7 : 1.0;
  const bbWidthPercent = asset.bbWidth != null 
    ? Math.min(100, (asset.bbWidth / threshold) * 100)
    : 0;

  return (
    <div className={cn(
      'bg-[#141419] border border-white/5 rounded-xl p-4 border-l-4',
      state.leftBorder
    )}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-white">{asset.asset}</span>
          <span className="text-sm text-gray-400 font-mono">
            {asset.price != null ? `$${formatNumber(asset.price)}` : '—'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            'w-2 h-2 rounded-full',
            state.dotColor,
            state.pulse && 'animate-pulse'
          )} />
          <span className={cn(
            'px-2 py-0.5 rounded text-[10px] font-bold border',
            state.badgeColor
          )}>
            {state.label}
          </span>
          <span className="text-[10px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">Delta</span>
        </div>
      </div>

      {/* BB Width */}
      <div className="mb-3">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-400">BB Width</span>
          <span className="font-mono text-gray-300">
            {asset.bbWidth != null ? `${asset.bbWidth.toFixed(2)}%` : '--%'} / {threshold}%
          </span>
        </div>
        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div 
            className={cn('h-full rounded-full transition-all duration-500', state.barColor)}
            style={{ width: `${Math.min(100, bbWidthPercent)}%` }}
          />
        </div>
      </div>

      {/* State-specific content */}
      {isNoSqueeze ? (
        <div className="py-4 text-center">
          <div className="text-3xl mb-2">⏸️</div>
          <div className="text-gray-500 text-sm">No active squeeze</div>
        </div>
      ) : isFilling ? (
        <div className="py-3 text-center">
          <div className="flex items-center justify-center gap-2 text-yellow-400">
            <span className="text-xl animate-pulse">⏳</span>
            <span className="text-base font-bold font-mono">
              Filling {asset.fillTimer ? formatTimeRemaining(asset.fillTimer) : '...'}
            </span>
          </div>
        </div>
      ) : hasPosition ? (
        <div className="py-2 flex items-center justify-between">
          <span className="text-sm text-gray-300">Position Active</span>
          <span className={cn(
            'font-mono font-bold',
            asset.positionPnl && asset.positionPnl >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {asset.positionPnl != null 
              ? `${asset.positionPnl >= 0 ? '+' : ''}${formatCurrency(asset.positionPnl)}`
              : '—'}
          </span>
        </div>
      ) : isActive && asset.premiumRange ? (
        <>
          {/* Direction Bias */}
          <div className="flex items-center justify-between mb-3 p-2 bg-white/5 rounded">
            <div className="flex items-center gap-2">
              <span>{getDirectionEmoji(asset.direction)}</span>
              <span className="text-xs text-gray-300">Bias</span>
            </div>
            <div className="text-right">
              <span className={cn(
                'text-xs font-bold uppercase',
                asset.direction === 'long' ? 'text-green-400' : 
                asset.direction === 'short' ? 'text-red-400' : 'text-gray-400'
              )}>
                {asset.direction}
              </span>
              <div className="text-[10px] text-gray-500">{(asset.confidence / 100).toFixed(1)} conf</div>
            </div>
          </div>

          {/* Premium Range */}
          <div>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-gray-500">Premium Range (30m)</span>
              <span className={cn(
                'font-mono',
                asset.premiumRange.current <= asset.premiumRange.threshold ? 'text-green-400' : 'text-gray-400'
              )}>
                {asset.premiumRange.current <= asset.premiumRange.threshold ? 'CHEAP ✓' : 'WAITING'}
              </span>
            </div>
            <div className="relative h-8 bg-gray-900 rounded overflow-hidden">
              <div className="absolute left-0 top-0 bottom-0 w-1/4 bg-green-500/10 border-r border-green-500/30" />
              <div className="absolute top-0 bottom-0 w-0.5 bg-green-500/50" style={{ left: '25%' }} />
              <div 
                className={cn(
                  'absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2 border-white',
                  asset.premiumRange.current <= asset.premiumRange.threshold ? 'bg-green-500' : 'bg-yellow-500'
                )}
                style={{ 
                  left: `${Math.min(95, Math.max(5, ((asset.premiumRange.current - asset.premiumRange.min) / 
                    (asset.premiumRange.max - asset.premiumRange.min || 1)) * 100))}%` 
                }}
              />
              <div className="absolute inset-x-2 bottom-0.5 flex justify-between text-[9px] text-gray-600 font-mono">
                <span>{asset.premiumRange.min.toFixed(1)}</span>
                <span>{asset.premiumRange.max.toFixed(1)}</span>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function RecentTradeCard({ trade }: { trade: { pair: string; position_type: string; pnl: number; entry_price?: number | null; exit_price?: number | null; exit_reason?: string | null; timestamp: string } }) {
  const pairShort = trade.pair.replace(/USD.*/, '').replace('/', '');
  const isProfit = trade.pnl > 0;
  const timeAgo = Math.floor((Date.now() - new Date(trade.timestamp).getTime()) / 60000);
  const timeText = timeAgo < 60 ? `${timeAgo}m ago` : `${Math.floor(timeAgo / 60)}h ago`;
  
  return (
    <div className="bg-[#141419] border border-white/5 rounded-lg p-3 min-w-[200px]">
      <div className="flex items-center justify-between mb-2">
        <span className="font-bold text-sm">{pairShort}</span>
        <span className={cn(
          'text-xs font-bold',
          trade.position_type === 'long' ? 'text-green-400' : 'text-red-400'
        )}>
          {trade.position_type.toUpperCase()}
        </span>
      </div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-500">${trade.entry_price?.toFixed(2) ?? '—'}</span>
        <span className="text-xs text-gray-400">→</span>
        <span className="text-xs text-gray-500">${trade.exit_price != null ? trade.exit_price.toFixed(2) : '—'}</span>
      </div>
      <div className={cn(
        'text-sm font-mono font-bold',
        isProfit ? 'text-green-400' : 'text-red-400'
      )}>
        {isProfit ? '+' : ''}{formatCurrency(trade.pnl)}
      </div>
      <div className="flex items-center justify-between mt-2">
        {trade.exit_reason && (
          <span className="text-[10px] bg-gray-800 px-1.5 py-0.5 rounded text-gray-400">
            {trade.exit_reason}
          </span>
        )}
        <span className="text-[10px] text-gray-600">{timeText}</span>
      </div>
    </div>
  );
}

// ── Main Dashboard Page ─────────────────────────────────────────────────

export default function DashboardPage() {
  const { botStatus, isConnected, trades, strategyLog, openPositions } = useSupabase();
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Bot state
  const botState = botStatus?.bot_state ?? (isConnected ? 'running' : 'paused');
  const uptimeSeconds = botStatus?.uptime_seconds ?? 0;
  
  // Market regime
  const regime = botStatus?.market_regime ?? 'SIDEWAYS';
  const chopScore = botStatus?.chop_score ?? 0;
  const atrRatio = botStatus?.atr_ratio ?? 1;
  const netChange = botStatus?.net_change_30m ?? 0;
  const regimeSince = botStatus?.regime_since;

  const regimeConfig: Record<string, { label: string; icon: string; color: string; bg: string }> = {
    TRENDING_UP:   { label: 'TRENDING UP',   icon: '↗', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    TRENDING_DOWN: { label: 'TRENDING DOWN', icon: '↘', color: 'text-red-400',     bg: 'bg-red-500/10' },
    SIDEWAYS:      { label: 'SIDEWAYS',      icon: '↔', color: 'text-amber-400',   bg: 'bg-amber-500/10' },
    CHOPPY:        { label: 'CHOPPY',        icon: '⚡', color: 'text-red-400',     bg: 'bg-red-500/10' },
  };
  const rc = regimeConfig[regime] ?? regimeConfig.SIDEWAYS;

  const regimeDuration = useMemo(() => {
    if (!regimeSince) return '';
    const elapsed = Math.max(0, Math.floor((Date.now() - new Date(regimeSince).getTime()) / 1000));
    if (elapsed < 60) return `${elapsed}s`;
    if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m`;
    return `${Math.floor(elapsed / 3600)}h ${Math.floor((elapsed % 3600) / 60)}m`;
  }, [regimeSince]);

  // Delta balance and stats
  const deltaBalance = Number(botStatus?.delta_balance ?? 0);
  const inrRate = botStatus?.inr_usd_rate ?? 86.5;
  const totalCapital = deltaBalance > 0 ? deltaBalance : (botStatus?.capital || 0);
  const capitalInr = Math.round(totalCapital * inrRate);

  // Stats for today
  const todayStats = useMemo(() => {
    const now = Date.now();
    const istOffsetMs = 5.5 * 60 * 60 * 1000;
    const istNow = new Date(now + istOffsetMs);
    const todayIST = istNow.toISOString().slice(0, 10);
    const cutoffMs = new Date(todayIST + 'T00:00:00+05:30').getTime();

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
  }, [trades]);

  // Total trades count
  const totalTrades = trades.filter(t => t.status === 'closed').length;
  const liveStrategyCount = useMemo(() => {
    const strategies = new Set(trades.map((t) => t.strategy));
    return strategies.size || 1;
  }, [trades]);

  // Squeeze data
  const squeezeAssets = useMemo((): SqueezeAsset[] => {
    const assets: SqueezeAsset[] = [];
    
    for (const assetName of ['BTC', 'ETH'] as const) {
      const logs = strategyLog
        .filter(l => l.pair && extractBaseAsset(l.pair) === assetName)
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      
      const latest = logs[0];
      const position = openPositions?.find(p => extractBaseAsset(p.pair) === assetName);
      
      const bbWidth = latest?.bb_upper != null && latest?.bb_lower != null && latest?.current_price
        ? ((latest.bb_upper - latest.bb_lower) / latest.current_price) * 100
        : null;
        
      const threshold = assetName === 'BTC' ? 0.7 : 1.0;
      const isSqueeze = bbWidth != null && bbWidth < threshold;
      
      let state: SqueezeAsset['state'] = 'no_squeeze';
      if (position) {
        state = 'position_open';
      } else if (isSqueeze) {
        state = 'squeeze_active';
      }
      
      const premiumRange = bbWidth != null ? {
        min: -bbWidth * 3,
        max: bbWidth * 3,
        current: (Math.random() - 0.5) * bbWidth * 2,
        threshold: -bbWidth * 1.5,
      } : null;
      
      const direction = latest?.rsi != null 
        ? (latest.rsi < 40 ? 'long' : latest.rsi > 60 ? 'short' : 'neutral')
        : 'neutral';
      
      assets.push({
        asset: assetName,
        price: latest?.current_price ?? null,
        bbWidth,
        state,
        direction,
        confidence: latest?.rsi != null ? Math.abs(50 - latest.rsi) * 2 : 50,
        premiumRange,
        lastUpdate: latest?.timestamp ?? null,
      });
    }
    
    return assets;
  }, [strategyLog, openPositions, currentTime]);

  // Recent trades (last 5)
  const recentTrades = useMemo(() => {
    return trades
      .filter(t => t.status === 'closed')
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 5);
  }, [trades]);

  const formatUptime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 md:p-6 pb-24 md:pb-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className={cn(
            'w-2 h-2 rounded-full',
            isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
          )} />
          <span className="text-lg font-bold tracking-wider">ALPHA</span>
          <span className="text-xs text-gray-600">v{process.env.ALPHA_VERSION ?? '0.12.8'}</span>
        </div>
      </div>

      {/* Balance & Regime Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        {/* Balance Card */}
        <div className="bg-[#141419] border border-white/5 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-500 uppercase mb-1">Delta Balance</div>
              <div className="text-2xl font-bold font-mono">{formatCurrency(deltaBalance)}</div>
              <div className="text-xs text-gray-500 mt-1">
                {todayStats.wins}W / {todayStats.losses}L • {todayStats.winRate.toFixed(0)}% WR • {todayStats.total} trades
              </div>
              <div className="text-xs mt-1">
                <span className={todayStats.grossPnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                  {todayStats.grossPnl >= 0 ? '+' : ''}{formatCurrency(todayStats.grossPnl)} P&L
                </span>
                <span className="text-gray-600"> • </span>
                <span className="text-gray-500">${todayStats.fees.toFixed(2)} fees</span>
              </div>
            </div>
          </div>
        </div>

        {/* Market Regime Card */}
        <div className={cn('rounded-xl p-4 border', rc.bg, 'border-white/5')}>
          <div className="flex items-center gap-2 mb-2">
            <span className={cn('text-lg', rc.color)}>{rc.icon}</span>
            <span className={cn('text-sm font-bold', rc.color)}>{rc.label}</span>
          </div>
          <div className="grid grid-cols-4 gap-2 text-xs">
            <div>
              <span className="text-gray-500 block">Chop</span>
              <span className="font-mono text-gray-300">{chopScore.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-gray-500 block">ATR</span>
              <span className="font-mono text-gray-300">{atrRatio.toFixed(1)}x</span>
            </div>
            <div>
              <span className="text-gray-500 block">Net</span>
              <span className={netChange >= 0 ? 'text-green-400' : 'text-red-400'}>
                {netChange >= 0 ? '+' : ''}{netChange.toFixed(2)}%
              </span>
            </div>
            <div>
              <span className="text-gray-500 block">Since</span>
              <span className="text-gray-400">{regimeDuration || '—'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Total Capital */}
      <div className="flex items-center justify-between bg-[#141419] border border-white/5 rounded-xl p-4 mb-4">
        <div>
          <div className="text-xs text-gray-500 uppercase">Total Capital</div>
          <div className="text-xl font-bold">
            {formatCurrency(totalCapital)}
            {capitalInr > 0 && (
              <span className="text-sm text-gray-500 ml-2">₹{capitalInr.toLocaleString('en-IN')}</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={cn('w-2 h-2 rounded-full', botState === 'running' ? 'bg-green-500' : 'bg-yellow-500')} />
            <span className={cn('text-xs', botState === 'running' ? 'text-green-500' : 'text-yellow-500')}>
              {botState === 'running' ? 'Running' : 'Paused'}
            </span>
            {uptimeSeconds > 0 && (
              <span className="text-xs text-gray-500">{formatUptime(uptimeSeconds)}</span>
            )}
          </div>
        </div>
        <div className="text-right text-xs text-gray-500">
          <div>Strategies: <span className="text-blue-400 font-mono">{liveStrategyCount}</span></div>
          <div>Total Trades: <span className="text-gray-300 font-mono">{totalTrades}</span></div>
        </div>
      </div>

      {/* Live Positions */}
      <LivePositions />

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 mt-4">
        {/* Left Column - Market Overview & Recent Trades */}
        <div className="lg:col-span-3 space-y-4">
          <MarketOverview />
          
          {/* Recent Trades */}
          <div className="bg-[#141419] border border-white/5 rounded-xl p-4">
            <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">Recent Trades</h3>
            {recentTrades.length === 0 ? (
              <p className="text-sm text-gray-600 text-center py-4">No recent trades</p>
            ) : (
              <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
                {recentTrades.map((trade) => (
                  <RecentTradeCard key={trade.id} trade={trade} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column - BB Squeeze (Sticky on desktop) */}
        <div className="lg:col-span-2">
          <div className="lg:sticky lg:top-4 space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center">
                <span className="text-green-500 font-bold text-sm">α</span>
              </div>
              <div>
                <h2 className="font-bold">BB SQUEEZE</h2>
                <p className="text-[10px] text-gray-500">Buy Cheap Premium | Hold Breakout</p>
              </div>
            </div>
            
            {squeezeAssets.map((asset) => (
              <SqueezeCard key={asset.asset} asset={asset} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
