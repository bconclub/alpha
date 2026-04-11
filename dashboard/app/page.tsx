'use client';

import { useState, useMemo, useEffect } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { formatCurrency, formatNumber, cn } from '@/lib/utils';
import { MarketOverview } from '@/components/dashboard/MarketOverview';
import { LivePositions } from '@/components/dashboard/LivePositions';
import { ArrowUp, ArrowDown, Scan } from 'lucide-react';

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
  // Signal panel redesign props
  strikePrice?: number;
  optionType?: 'CALL' | 'PUT';
  callPremium?: number;
  putPremium?: number;
  // Breakout state from options_state
  breakoutState?: 'NONE' | 'DETECTED' | 'CONFIRMED' | 'FAKEOUT' | 'OVERPRICED' | 'BREAKOUT_NO_FILL';
  breakoutDirection?: 'UP' | 'DOWN';
  breakoutVelocity?: number;
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
        badgeColor: 'bg-purple-500 text-white border-purple-500',
        dotColor: 'bg-purple-500',
        barColor: 'bg-purple-500',
        leftBorder: 'border-l-purple-500',
        pulse: false,
      };
    case 'filling':
      return {
        label: 'ENTERING...',
        badgeColor: 'bg-amber-500 text-black border-amber-500 animate-pulse',
        dotColor: 'bg-amber-500',
        barColor: 'bg-amber-500',
        leftBorder: 'border-l-amber-500',
        pulse: true,
      };
    case 'squeeze_active':
      return {
        label: 'SQUEEZE READY',
        badgeColor: 'bg-green-500 text-white border-green-500',
        dotColor: 'bg-green-500',
        barColor: 'bg-green-500',
        leftBorder: 'border-l-green-500',
        pulse: false,
      };
    default:
      return {
        label: 'MONITORING',
        badgeColor: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
        dotColor: 'bg-blue-500',
        barColor: 'bg-amber-500',
        leftBorder: 'border-l-blue-500',
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

function getLastScanSeconds(lastUpdate: string | null): number {
  if (!lastUpdate) return 999;
  return Math.floor((Date.now() - new Date(lastUpdate).getTime()) / 1000);
}

// ── Components ──────────────────────────────────────────────────────────

function SqueezeCard({ asset }: { asset: SqueezeAsset }) {
  const state = getStateConfig(asset.state);
  const lastScanSecs = getLastScanSeconds(asset.lastUpdate);
  
  // Determine which option is cheaper
  const isCallCheaper = asset.callPremium != null && asset.putPremium != null 
    ? asset.callPremium <= asset.putPremium 
    : true;
  const cheaperPremium = isCallCheaper ? asset.callPremium : asset.putPremium;
  
  // Signal strength bar color based on confidence
  const getSignalColor = (confidence: number) => {
    if (confidence < 50) return 'bg-red-500';
    if (confidence < 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };
  
  // Breakout status display
  const getBreakoutDisplay = () => {
    const { breakoutState, breakoutDirection, breakoutVelocity } = asset;
    
    switch (breakoutState) {
      case 'DETECTED':
        const arrow = breakoutDirection === 'UP' ? '↑' : '↓';
        const color = breakoutDirection === 'UP' ? 'text-green-500' : 'text-red-500';
        return { 
          label: `DETECTED ${breakoutDirection} ${arrow}`, 
          color,
          extra: breakoutVelocity ? `${breakoutVelocity.toFixed(2)}%` : undefined
        };
      case 'CONFIRMED':
        return { label: 'CONFIRMED ✓', color: 'text-green-500' };
      case 'FAKEOUT':
      case 'BREAKOUT_NO_FILL':
        return { label: 'FAKEOUT ✗', color: 'text-red-500' };
      case 'OVERPRICED':
        return { label: 'OVERPRICED ✗', color: 'text-amber-500' };
      default:
        return { label: 'NONE', color: 'text-gray-500' };
    }
  };
  
  const breakoutDisplay = getBreakoutDisplay();
  const directionLabel = asset.direction === 'long'
    ? 'CALL bias'
    : asset.direction === 'short'
      ? 'PUT bias'
      : 'Neutral bias';
  const watchLabel = asset.state === 'position_open'
    ? 'Managing open breakout'
    : asset.breakoutState === 'DETECTED'
      ? 'Watch for breakout confirmation'
      : asset.breakoutState === 'CONFIRMED'
        ? 'Breakout already confirmed'
        : asset.state === 'squeeze_active'
          ? 'Watch for expansion from squeeze'
          : 'Waiting for squeeze setup';
  const scanLabel = lastScanSecs < 60
    ? `${lastScanSecs}s ago`
    : `${Math.floor(lastScanSecs / 60)}m ${lastScanSecs % 60}s ago`;

  return (
    <div className={cn(
      'rounded-2xl bg-[linear-gradient(180deg,#171821_0%,#101117_100%)] p-4 border-l-4 shadow-[0_18px_44px_rgba(0,0,0,0.28)]',
      state.leftBorder
    )}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-white">{asset.asset}</span>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-gray-400">
            Strategy View
          </span>
          <span className="text-sm text-gray-400 font-mono">
            {asset.price != null ? `$${formatNumber(asset.price)}` : '—'}
          </span>
        </div>
        
        <div className="flex flex-col items-end gap-2">
          <span className={cn(
            'w-2 h-2 rounded-full',
            state.dotColor,
            state.pulse && 'animate-pulse'
          )} />
          <span className={cn(
            'px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.2em] rounded-full border',
            state.badgeColor
          )}>
            {state.label}
          </span>
          <span className="text-[11px] text-gray-500">Live scan {scanLabel}</span>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div className="rounded-xl bg-black/10 p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-gray-500">Market At</p>
          <p className="mt-2 text-lg font-semibold text-white">
            {asset.strikePrice ? `$${asset.strikePrice.toLocaleString()}` : 'No strike'}
          </p>
          <p className="mt-1 text-xs text-gray-400">ATM strike</p>
        </div>

        <div className="rounded-xl bg-black/10 p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-gray-500">Bias</p>
          <p className="mt-2 flex items-center gap-2 text-sm font-semibold text-white">
            <span>{getDirectionEmoji(asset.direction)}</span>
            <span>{directionLabel}</span>
          </p>
          <p className="mt-1 text-xs text-gray-400">{watchLabel}</p>
        </div>

        <div className="rounded-xl bg-black/10 p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-gray-500">Breakout</p>
          <p className={cn('mt-2 text-sm font-semibold', breakoutDisplay.color)}>
            {breakoutDisplay.label}
          </p>
          <p className="mt-1 text-xs text-gray-400">
            {breakoutDisplay.extra ?? 'No breakout pressure right now'}
          </p>
        </div>
      </div>

      {/* 2. Signal strength bar */}
      <div className="mb-4 rounded-xl bg-white/[0.03] p-3">
        <div className="flex justify-between text-xs mb-2">
          <span className="text-gray-400 uppercase tracking-[0.18em]">Signal Strength</span>
          <span className="font-mono text-white">{asset.confidence.toFixed(0)}%</span>
        </div>
        <div className="relative h-2 bg-gray-800 rounded-full overflow-hidden">
          <div 
            className={cn("h-full rounded-full transition-all duration-500", getSignalColor(asset.confidence))}
            style={{ width: `${Math.min(100, asset.confidence)}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-white/[0.03] p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-gray-500">Going After</p>
          {cheaperPremium != null ? (
            <div className="mt-2 flex items-center gap-2">
              {isCallCheaper ? (
                <>
                  <ArrowUp className="w-4 h-4 text-green-500" />
                  <span className="text-sm font-bold text-green-400">CALL</span>
                  <span className="text-lg font-mono font-bold text-white">${cheaperPremium}</span>
                </>
              ) : (
                <>
                  <ArrowDown className="w-4 h-4 text-red-500" />
                  <span className="text-sm font-bold text-red-400">PUT</span>
                  <span className="text-lg font-mono font-bold text-white">${cheaperPremium}</span>
                </>
              )}
            </div>
          ) : (
            <p className="mt-2 text-sm text-gray-400">Premium not available</p>
          )}
          <p className="mt-1 text-xs text-gray-500">Cheaper premium side</p>
        </div>

        <div className="rounded-xl bg-black/10 p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-gray-500">What To Watch</p>
          <p className={cn('mt-2 text-sm font-semibold', breakoutDisplay.color)}>{breakoutDisplay.label}</p>
          <p className="mt-1 text-xs text-gray-400">{breakoutDisplay.extra ?? watchLabel}</p>
        </div>
      </div>
    </div>
  );
}

function RecentTradeCard({ trade }: { trade: { pair: string; position_type: string; option_side?: 'call' | 'put' | null; pnl: number; entry_price?: number | null; exit_price?: number | null; exit_reason?: string | null; timestamp: string } }) {
  const pairShort = trade.pair.replace(/USD.*/, '').replace('/', '');
  const isProfit = trade.pnl > 0;
  const timeAgo = Math.floor((Date.now() - new Date(trade.timestamp).getTime()) / 60000);
  const timeText = timeAgo < 60 ? `${timeAgo}m ago` : `${Math.floor(timeAgo / 60)}h ago`;
  
  // Determine option side: use option_side field or extract from pair symbol
  const getOptionSide = (): { label: string; isCall: boolean } => {
    // If option_side is explicitly set, use it
    if (trade.option_side) {
      return { 
        label: trade.option_side === 'call' ? 'CALL' : 'PUT',
        isCall: trade.option_side === 'call'
      };
    }
    
    // Fallback: extract from pair symbol (e.g., "ETH-27MAR25-2100-P" or "ETH 2040P")
    const pairUpper = trade.pair.toUpperCase();
    if (pairUpper.endsWith('-C') || pairUpper.endsWith('C') || pairUpper.includes('-CALL')) {
      return { label: 'CALL', isCall: true };
    }
    if (pairUpper.endsWith('-P') || pairUpper.endsWith('P') || pairUpper.includes('-PUT')) {
      return { label: 'PUT', isCall: false };
    }
    
    // Default based on position_type (legacy fallback)
    return { 
      label: trade.position_type === 'long' ? 'CALL' : 'PUT',
      isCall: trade.position_type === 'long'
    };
  };
  
  const optionDisplay = getOptionSide();
  
  return (
    <div className="bg-[#141419] border border-white/5 rounded-lg p-3 min-w-[200px]">
      <div className="flex items-center justify-between mb-2">
        <span className="font-bold text-sm">{pairShort}</span>
        <span className={cn(
          'text-xs font-bold px-2 py-0.5 rounded',
          optionDisplay.isCall ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
        )}>
          {optionDisplay.label}
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
  const { botStatus, isConnected, trades, strategyLog, openPositions, optionsState } = useSupabase();
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

  // Squeeze data with options_state integration
  const squeezeAssets = useMemo((): SqueezeAsset[] => {
    const assets: SqueezeAsset[] = [];
    
    for (const assetName of ['BTC', 'ETH'] as const) {
      const pair = `${assetName}/USD:USD`;
      const logs = strategyLog
        .filter(l => l.pair && extractBaseAsset(l.pair) === assetName)
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      
      const latest = logs[0];
      const position = openPositions?.find(p => extractBaseAsset(p.pair) === assetName);
      
      // Get options_state for this pair
      const optState = optionsState?.find(s => s.pair === pair);
      
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
      
      // Extract strike and option type from position if available
      const strikePrice = optState?.atm_strike ?? position?.stop_loss ?? undefined;
      const optionType = position?.pair?.endsWith('-C') ? 'CALL' : 
                        position?.pair?.endsWith('-P') ? 'PUT' : undefined;
      
      // Get premiums from options_state
      const callPremium = optState?.call_premium ?? undefined;
      const putPremium = optState?.put_premium ?? undefined;
      
      // Get breakout state from options_state
      const breakoutState = optState?.breakout_state as SqueezeAsset['breakoutState'] ?? 'NONE';
      const breakoutDirection = optState?.breakout_direction as SqueezeAsset['breakoutDirection'] ?? undefined;
      const breakoutVelocity = optState?.breakout_velocity_pct ?? undefined;
      
      assets.push({
        asset: assetName,
        price: latest?.current_price ?? null,
        bbWidth,
        state,
        direction,
        confidence: latest?.rsi != null ? Math.abs(50 - latest.rsi) * 2 : 50,
        premiumRange,
        lastUpdate: latest?.timestamp ?? null,
        strikePrice,
        optionType,
        callPremium,
        putPremium,
        breakoutState,
        breakoutDirection,
        breakoutVelocity,
      });
    }
    
    return assets;
  }, [strategyLog, openPositions, optionsState, currentTime]);

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

  // Timeframe selection for Total Capital card
  const [capitalTimeframe, setCapitalTimeframe] = useState<'24h' | '7d' | '14d' | '30d'>('24h');
  
  // Calculate P&L for selected timeframe
  const timeframeStats = useMemo(() => {
    const now = Date.now();
    const istOffsetMs = 5.5 * 60 * 60 * 1000;
    
    let cutoffMs: number;
    if (capitalTimeframe === '24h') {
      const istNow = new Date(now + istOffsetMs);
      const todayIST = istNow.toISOString().slice(0, 10);
      cutoffMs = new Date(todayIST + 'T00:00:00+05:30').getTime();
    } else {
      const days = capitalTimeframe === '7d' ? 7 : capitalTimeframe === '14d' ? 14 : 30;
      cutoffMs = now - days * 24 * 60 * 60 * 1000;
    }

    let pnl = 0;
    let total = 0;
    
    for (const t of trades) {
      if (t.status !== 'closed') continue;
      const tradeTime = new Date(t.timestamp).getTime();
      if (tradeTime >= cutoffMs) {
        pnl += t.pnl ?? 0;
        total++;
      }
    }
    
    return { pnl, total };
  }, [trades, capitalTimeframe]);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-3 sm:p-4 md:p-6 pb-24 md:pb-6">
      {/* 2-Card Row: Total Capital + Timeframe | Market Regime */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        {/* Card 1: Total Capital + Timeframe Toggle */}
        <div className="bg-[#141419] border border-white/5 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 uppercase tracking-wider">Total Capital</span>
            <div className="flex gap-1">
              {(['24h', '7d', '14d', '30d'] as const).map((tf) => (
                <button
                  key={tf}
                  onClick={() => setCapitalTimeframe(tf)}
                  className={cn(
                    'px-2 py-0.5 text-[10px] font-medium rounded transition-colors',
                    capitalTimeframe === tf
                      ? 'bg-white/10 text-white'
                      : 'border border-white/10 text-gray-500 hover:text-gray-300'
                  )}
                >
                  {tf.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="text-2xl font-bold font-mono">
            {formatCurrency(totalCapital)}
          </div>
          {capitalInr > 0 && (
            <div className="text-xs text-gray-500">₹{capitalInr.toLocaleString('en-IN')}</div>
          )}
          <div className="flex items-center justify-between mt-2">
            <div className="flex items-center gap-2">
              <span className={cn('w-2 h-2 rounded-full', botState === 'running' ? 'bg-green-500' : 'bg-yellow-500')} />
              <span className={cn('text-xs', botState === 'running' ? 'text-green-500' : 'text-yellow-500')}>
                {botState === 'running' ? 'Running' : 'Paused'}
              </span>
              {uptimeSeconds > 0 && (
                <span className="text-xs text-gray-500">{formatUptime(uptimeSeconds)}</span>
              )}
            </div>
            {timeframeStats.total > 0 && (
              <span className={cn(
                'text-xs font-mono font-bold',
                timeframeStats.pnl >= 0 ? 'text-green-400' : 'text-red-400'
              )}>
                {timeframeStats.pnl >= 0 ? '+' : ''}{formatCurrency(timeframeStats.pnl)}
              </span>
            )}
          </div>
        </div>

        {/* Card 3: Market Regime */}
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
            {squeezeAssets.map((asset) => (
              <SqueezeCard key={asset.asset} asset={asset} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
