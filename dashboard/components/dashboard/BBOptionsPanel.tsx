'use client';

import { useMemo, useState, useEffect, useRef, useCallback } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn } from '@/lib/utils';
import type { OptionsState, ActivityLogRow, OpenPosition, BotStatus } from '@/lib/types';

// ═══════════════════════════════════════════════════════════════
// GLOBAL STYLES — Inject animations
// ═══════════════════════════════════════════════════════════════

const STYLE_ID = '__bb-squeeze-styles';

function ensureStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;
  
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    @keyframes squeezePulse {
      0%, 100% { box-shadow: 0 0 20px rgba(0,255,136,0.2); }
      50% { box-shadow: 0 0 40px rgba(0,255,136,0.4); }
    }
    .squeeze-pulse-active {
      animation: squeezePulse 2s ease-in-out infinite;
    }
    @keyframes fillRingProgress {
      from { stroke-dashoffset: 283; }
      to { stroke-dashoffset: var(--progress-offset, 0); }
    }
  `;
  document.head.appendChild(style);
}

// ═══════════════════════════════════════════════════════════════
// DESIGN TOKENS — Sleek Dark Crypto Theme
// ═══════════════════════════════════════════════════════════════

const COLORS = {
  bg: '#0a0a0f',
  card: '#141419',
  cardElevated: '#1a1a22',
  border: 'rgba(255,255,255,0.05)',
  textPrimary: '#ffffff',
  textSecondary: '#8b8b9a',
  textMuted: '#5a5a6a',
  
  // Squeeze states
  squeezeActive: '#00ff88',
  squeezeForming: '#ffb800',
  squeezeNone: '#ff4757',
  
  // Premium
  premiumCheap: '#00ff88',
  premiumExpensive: '#ff4757',
  
  // Directions
  long: '#00ff88',
  short: '#ff4757',
  neutral: '#8b8b9a',
  
  // Accents
  accentBlue: '#00d2ff',
  accentPurple: '#7c4dff',
};

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface BBOptionsPanelProps {
  asset: string;
  state: OptionsState | null;
  openTrade: OpenPosition | null;
  recentEvents: ActivityLogRow[];
  botStatus: BotStatus | null;
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function fmtPrice(v: number | null): string {
  if (v == null) return '—';
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function fmtPremium(v: number | null): string {
  if (v == null || v <= 0) return '—';
  return `$${v.toFixed(2)}`;
}

function fmtPremium4(v: number | null): string {
  if (v == null || v <= 0) return '—';
  return `$${v.toFixed(4)}`;
}

function fmtPct(v: number | null): string {
  if (v == null) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function useLiveTick(intervalMs = 1000) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return tick;
}

// ═══════════════════════════════════════════════════════════════
// 1. ASSET HEADER
// ═══════════════════════════════════════════════════════════════

function AssetHeader({ 
  name, 
  price, 
  balance, 
  status 
}: { 
  name: string; 
  price: number | null; 
  balance: number | null; 
  status: 'LIVE' | 'STALE' | 'DEAD';
}) {
  const statusConfig = {
    LIVE: { dot: 'bg-[#00ff88]', pulse: true, text: 'text-[#00ff88]' },
    STALE: { dot: 'bg-[#ffb800]', pulse: false, text: 'text-[#ffb800]' },
    DEAD: { dot: 'bg-[#ff4757]', pulse: false, text: 'text-[#ff4757]' },
  };
  const cfg = statusConfig[status];
  
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold tracking-tight" style={{ color: COLORS.textPrimary }}>
            {name}
          </span>
          <span className="text-lg font-medium text-[#8b8b9a]" style={{ fontFamily: 'Inter, system-ui', fontVariantNumeric: 'tabular-nums' }}>
            {fmtPrice(price)}
          </span>
        </div>
        
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-[#00d2ff]/10 border border-[#00d2ff]/20">
          <span className={cn('w-1.5 h-1.5 rounded-full', cfg.dot, cfg.pulse && 'animate-pulse')} />
          <span className={cn('text-[10px] font-semibold uppercase tracking-wider', cfg.text)}>
            {status}
          </span>
        </div>
      </div>
      
      <div className="flex items-center gap-3">
        {balance != null && (
          <div className="text-right">
            <div className="text-[10px] text-[#5a5a6a] uppercase tracking-wider">Balance</div>
            <div className="text-sm font-semibold text-white" style={{ fontVariantNumeric: 'tabular-nums' }}>
              ${balance.toFixed(2)}
            </div>
          </div>
        )}
        <div className="px-2 py-1 rounded bg-[#7c4dff]/10 border border-[#7c4dff]/20">
          <span className="text-[10px] font-semibold text-[#7c4dff]">Delta</span>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 2. FILL COUNTDOWN — Progress ring for 5-min fill timer
// ═══════════════════════════════════════════════════════════════

function FillCountdown({ 
  secondsRemaining, 
  totalSeconds = 300 // 5 minutes
}: { 
  secondsRemaining: number; 
  totalSeconds?: number;
}) {
  const progress = Math.max(0, Math.min(100, (secondsRemaining / totalSeconds) * 100));
  const offset = 283 - (283 * progress) / 100;
  
  const mins = Math.floor(secondsRemaining / 60);
  const secs = secondsRemaining % 60;
  
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl bg-[#0a0a0f]/50 border border-[rgba(255,255,255,0.05)]">
      <div className="relative w-12 h-12">
        <svg className="w-12 h-12 -rotate-90" viewBox="0 0 100 100">
          {/* Background ring */}
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="rgba(255,255,255,0.1)"
            strokeWidth="8"
          />
          {/* Progress ring */}
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="#00ff88"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray="283"
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 1s linear' }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[10px] font-mono font-bold text-white">
            {mins}:{secs.toString().padStart(2, '0')}
          </span>
        </div>
      </div>
      <div>
        <div className="text-xs font-medium text-white">Filling Order...</div>
        <div className="text-[10px] text-[#8b8b9a]">Limit @ cheap threshold</div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 3. SQUEEZE VISUALIZER
// ═══════════════════════════════════════════════════════════════

function SqueezeVisualizer({
  bbWidth,
  bbWidthMax,
  kcContainsBB,
  isActive,
}: {
  bbWidth: number | null;
  bbWidthMax: number | null;
  kcContainsBB: boolean;
  isActive: boolean;
}) {
  const widthPct = bbWidth != null && bbWidthMax != null && bbWidthMax > 0
    ? Math.min((bbWidth / bbWidthMax) * 100, 100)
    : 0;
  
  // Determine squeeze state
  const isForming = !isActive && bbWidth != null && bbWidthMax != null && bbWidth < bbWidthMax * 1.5;
  
  const glowClass = isActive ? 'squeeze-pulse-active' : '';
  
  const barColor = isActive 
    ? 'from-[#00ff88] to-[#00c853]'
    : isForming 
      ? 'from-[#ffb800] to-[#ff9500]'
      : 'from-[#ff4757] to-[#ff2d55]';
  
  const statusText = isActive 
    ? 'SQUEEZE ACTIVE'
    : isForming 
      ? 'FORMING'
      : 'NO SQUEEZE';
  
  const statusColor = isActive 
    ? 'text-[#00ff88]'
    : isForming 
      ? 'text-[#ffb800]'
      : 'text-[#ff4757]';

  return (
    <div 
      className={cn(
        'rounded-xl p-4 mb-4 border transition-all duration-300',
        glowClass
      )}
      style={{ 
        background: COLORS.card,
        borderColor: isActive ? 'rgba(0,255,136,0.3)' : COLORS.border,
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#8b8b9a]">
          BB Squeeze
        </span>
        <span className={cn('text-xs font-bold uppercase tracking-wider', statusColor)}>
          {statusText}
        </span>
      </div>
      
      {/* BB Width Bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] text-[#5a5a6a]">BB Width</span>
          <span className="text-xs font-mono font-medium text-white">
            {bbWidth?.toFixed(2) ?? '—'}% / {bbWidthMax ?? '—'}%
          </span>
        </div>
        <div className="relative h-2.5 rounded-full bg-[#0a0a0f] overflow-hidden">
          <div 
            className={cn('absolute inset-y-0 left-0 rounded-full bg-gradient-to-r transition-all duration-500', barColor)}
            style={{ width: `${widthPct}%` }}
          />
          {/* Threshold marker */}
          {bbWidthMax != null && (
            <div 
              className="absolute inset-y-0 w-0.5 bg-white/30"
              style={{ left: '100%' }}
            />
          )}
        </div>
      </div>
      
      {/* KC Contains BB indicator */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#0a0a0f]/50">
        <span className="text-[10px] text-[#8b8b9a]">Keltner Channel Contains BB</span>
        <span className={cn(
          'text-xs font-bold uppercase',
          kcContainsBB ? 'text-[#00ff88]' : 'text-[#ff4757]'
        )}>
          {kcContainsBB ? '✓ YES' : '✗ NO'}
        </span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 4. PREMIUM RANGE
// ═══════════════════════════════════════════════════════════════

function PremiumRange({
  min,
  max,
  current,
  threshold,
  isCheap,
}: {
  min: number | null;
  max: number | null;
  current: number | null;
  threshold: number | null;
  isCheap: boolean;
}) {
  const range = max != null && min != null && max > min ? max - min : 0;
  const currentPos = current != null && min != null && range > 0
    ? Math.min(Math.max(((current - min) / range) * 100, 0), 100)
    : 50;
  const thresholdPos = threshold != null && min != null && range > 0
    ? Math.min(Math.max(((threshold - min) / range) * 100, 0), 100)
    : 25;

  return (
    <div 
      className="rounded-xl p-4 mb-4 border"
      style={{ 
        background: COLORS.card,
        borderColor: COLORS.border,
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#8b8b9a]">
          Premium Range (30min)
        </span>
        {isCheap ? (
          <span className="text-xs font-bold text-[#00ff88]">✓ CHEAP ENOUGH</span>
        ) : (
          <span className="text-xs font-bold text-[#ffb800]">WAITING...</span>
        )}
      </div>
      
      {/* Range bar */}
      <div className="relative mb-4">
        {/* Min/Max labels */}
        <div className="flex items-center justify-between text-[10px] text-[#5a5a6a] mb-1">
          <span>{fmtPremium4(min)}</span>
          <span>{fmtPremium4(max)}</span>
        </div>
        
        {/* Bar background */}
        <div className="relative h-3 rounded-full bg-[#0a0a0f] overflow-hidden">
          {/* Gradient fill showing cheap zone */}
          <div 
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-[#00ff88]/30 to-transparent"
            style={{ width: `${thresholdPos}%` }}
          />
          
          {/* Threshold marker */}
          <div 
            className="absolute inset-y-0 w-0.5 bg-[#00ff88]"
            style={{ left: `${thresholdPos}%` }}
          />
          
          {/* Current position marker */}
          <div 
            className={cn(
              'absolute top-1/2 w-3 h-3 rounded-full border-2 shadow-[0_0_8px_rgba(255,255,255,0.3)]',
              isCheap 
                ? 'bg-[#00ff88] border-[#00ff88]' 
                : 'bg-[#ffb800] border-[#ffb800]'
            )}
            style={{ 
              left: `${currentPos}%`, 
              transform: `translateX(-50%) translateY(-50%)`,
              transition: 'left 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          />
        </div>
        
        {/* Current value label */}
        <div className="flex items-center justify-center mt-2">
          <span className="text-xs font-mono font-medium text-white">
            Current: {fmtPremium4(current)}
          </span>
        </div>
      </div>
      
      {/* Threshold info */}
      <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#0a0a0f]/50">
        <span className="text-[10px] text-[#8b8b9a]">Cheap Threshold (25%)</span>
        <span className="text-xs font-mono font-medium text-[#00ff88]">
          {fmtPremium4(threshold)}
        </span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 5. DIRECTION BIAS
// ═══════════════════════════════════════════════════════════════

function DirectionBias({
  bbPosition,
  bias,
  confidence,
}: {
  bbPosition: number | null;
  bias: 'LONG' | 'SHORT' | 'NEUTRAL' | null;
  confidence: number | null;
}) {
  const positionLabel = bbPosition != null
    ? bbPosition < 0.4 
      ? 'Lower Half' 
      : bbPosition > 0.6 
        ? 'Upper Half' 
        : 'Middle'
    : '—';
  
  const biasConfig = {
    LONG: { color: 'text-[#00ff88]', bg: 'bg-[#00ff88]/10', border: 'border-[#00ff88]/30', icon: '▲' },
    SHORT: { color: 'text-[#ff4757]', bg: 'bg-[#ff4757]/10', border: 'border-[#ff4757]/30', icon: '▼' },
    NEUTRAL: { color: 'text-[#8b8b9a]', bg: 'bg-[#8b8b9a]/10', border: 'border-[#8b8b9a]/30', icon: '—' },
  };
  
  const cfg = bias != null && bias in biasConfig ? biasConfig[bias] : biasConfig.NEUTRAL;
  
  const confidenceLabel = confidence != null
    ? confidence >= 0.8 
      ? 'High' 
      : confidence >= 0.6 
        ? 'Medium' 
        : 'Low'
    : '—';

  return (
    <div 
      className="rounded-xl p-4 mb-4 border"
      style={{ 
        background: COLORS.card,
        borderColor: COLORS.border,
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#8b8b9a]">
          Direction Bias
        </span>
      </div>
      
      <div className="space-y-3">
        {/* BB Position */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-[#8b8b9a]">BB Position</span>
          <span className="text-xs font-mono text-white">
            {bbPosition?.toFixed(2) ?? '—'} ({positionLabel})
          </span>
        </div>
        
        {/* BB Position visual bar */}
        <div className="relative h-1.5 rounded-full bg-gradient-to-r from-[#00ff88]/30 via-[#8b8b9a]/30 to-[#ff4757]/30">
          {bbPosition != null && (
            <div 
              className="absolute top-1/2 w-2 h-2 rounded-full bg-white shadow-[0_0_4px_rgba(255,255,255,0.5)]"
              style={{ 
                left: `${Math.max(0, Math.min(100, bbPosition * 100))}%`,
                transform: 'translateX(-50%) translateY(-50%)',
              }}
            />
          )}
        </div>
        
        {/* Bias badge */}
        <div className="flex items-center justify-between pt-1">
          <span className="text-[10px] text-[#8b8b9a]">Bias</span>
          <div className={cn(
            'flex items-center gap-1.5 px-3 py-1 rounded-full border',
            cfg.bg, cfg.border
          )}>
            <span className={cn('text-xs', cfg.color)}>{cfg.icon}</span>
            <span className={cn('text-xs font-bold uppercase', cfg.color)}>
              {bias ?? 'NEUTRAL'}
            </span>
          </div>
        </div>
        
        {/* Confidence */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-[#8b8b9a]">Confidence</span>
          <span className="text-xs font-mono text-white">
            {confidence?.toFixed(1) ?? '—'} ({confidenceLabel})
          </span>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 6. PREMIUM GRID
// ═══════════════════════════════════════════════════════════════

function PremiumGrid({
  callPremium,
  putPremium,
  selectedSide,
  orderStatus,
  fillTimer,
}: {
  callPremium: number | null;
  putPremium: number | null;
  selectedSide: 'CALL' | 'PUT' | null;
  orderStatus: 'IDLE' | 'PENDING_FILL' | 'FILLED' | null;
  fillTimer: string | null;
}) {
  const callActive = selectedSide === 'CALL';
  const putActive = selectedSide === 'PUT';
  
  return (
    <div className="grid grid-cols-2 gap-3 mb-4">
      {/* CALL */}
      <div 
        className={cn(
          'rounded-xl p-3 border transition-all duration-300',
          callActive 
            ? 'bg-[#00ff88]/5 border-[#00ff88]/30' 
            : 'bg-[#141419] border-[rgba(255,255,255,0.05)]'
        )}
      >
        <div className="flex items-center justify-between mb-2">
          <span className={cn(
            'text-xs font-bold uppercase tracking-wider',
            callActive ? 'text-[#00ff88]' : 'text-[#5a5a6a]'
          )}>
            CALL
          </span>
          {callActive && orderStatus === 'PENDING_FILL' && (
            <span className="w-1.5 h-1.5 rounded-full bg-[#00ff88] animate-pulse" />
          )}
        </div>
        <div className="text-lg font-bold text-white mb-1" style={{ fontVariantNumeric: 'tabular-nums' }}>
          {fmtPremium(callPremium)}
        </div>
        {callActive && orderStatus === 'PENDING_FILL' && fillTimer && (
          <div className="text-[10px] text-[#ffb800]">
            Filling... {fillTimer}
          </div>
        )}
        {callActive && orderStatus === 'IDLE' && (
          <div className="text-[10px] text-[#5a5a6a]">
            Waiting for squeeze...
          </div>
        )}
      </div>
      
      {/* PUT */}
      <div 
        className={cn(
          'rounded-xl p-3 border transition-all duration-300',
          putActive 
            ? 'bg-[#ff4757]/5 border-[#ff4757]/30' 
            : 'bg-[#141419] border-[rgba(255,255,255,0.05)]'
        )}
      >
        <div className="flex items-center justify-between mb-2">
          <span className={cn(
            'text-xs font-bold uppercase tracking-wider',
            putActive ? 'text-[#ff4757]' : 'text-[#5a5a6a]'
          )}>
            PUT
          </span>
          {putActive && orderStatus === 'PENDING_FILL' && (
            <span className="w-1.5 h-1.5 rounded-full bg-[#ff4757] animate-pulse" />
          )}
        </div>
        <div className="text-lg font-bold text-white mb-1" style={{ fontVariantNumeric: 'tabular-nums' }}>
          {fmtPremium(putPremium)}
        </div>
        {putActive && orderStatus === 'PENDING_FILL' && fillTimer && (
          <div className="text-[10px] text-[#ffb800]">
            Filling... {fillTimer}
          </div>
        )}
        {putActive && orderStatus === 'IDLE' && (
          <div className="text-[10px] text-[#5a5a6a]">
            Waiting for squeeze...
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 7. LAST EXIT
// ═══════════════════════════════════════════════════════════════

function LastExit({
  exitType,
  pnl,
  pnlPct,
}: {
  exitType: string | null;
  pnl: number | null;
  pnlPct: number | null;
}) {
  if (!exitType) return null;
  
  const isProfit = (pnlPct ?? 0) >= 0;
  
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-[#0a0a0f]/50">
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-[#5a5a6a]">Last:</span>
        <span className="text-xs font-medium text-[#8b8b9a]">{exitType}</span>
      </div>
      <div className={cn(
        'text-xs font-mono font-medium',
        isProfit ? 'text-[#00ff88]' : 'text-[#ff4757]'
      )}>
        {fmtPct(pnlPct)} ({pnl != null ? `$${pnl >= 0 ? '+' : ''}${pnl.toFixed(4)}` : '—'})
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 8. POSITION CARD (When in position)
// ═══════════════════════════════════════════════════════════════

function PositionCard({
  side,
  strike,
  entryPremium,
  currentPremium,
  pnlPct,
  pnlUsd,
  highestPremium,
  trailingActive,
  openedAt,
}: {
  side: string;
  strike: number | null;
  entryPremium: number | null;
  currentPremium: number | null;
  pnlPct: number | null;
  pnlUsd: number | null;
  highestPremium: number | null;
  trailingActive: boolean;
  openedAt: string | null;
}) {
  useLiveTick();
  
  const holdSec = openedAt ? Math.floor((Date.now() - new Date(openedAt).getTime()) / 1000) : 0;
  const holdMin = Math.floor(holdSec / 60);
  const holdRemSec = holdSec % 60;
  
  const peakPct = highestPremium != null && entryPremium != null && entryPremium > 0
    ? ((highestPremium - entryPremium) / entryPremium * 100)
    : null;
  
  const phase = holdSec < 30 ? 1 : 2;
  
  const sideColor = side === 'call' ? 'text-[#00ff88]' : 'text-[#ff4757]';
  const sideBg = side === 'call' ? 'bg-[#00ff88]/10 border-[#00ff88]/30' : 'bg-[#ff4757]/10 border-[#ff4757]/30';
  
  return (
    <div 
      className={cn(
        'rounded-xl p-4 mb-4 border',
        sideBg
      )}
      style={{ boxShadow: side === 'call' ? '0 0 30px rgba(0,255,136,0.1)' : '0 0 30px rgba(255,71,87,0.1)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={cn('text-sm font-bold uppercase tracking-wider', sideColor)}>
            {side} {strike != null ? `$${strike.toLocaleString()}` : ''}
          </span>
          {trailingActive && (
            <span className="flex items-center gap-1 text-[10px] font-mono text-[#00ff88]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#00ff88] animate-pulse" />
              TRAILING
            </span>
          )}
        </div>
        <span className="text-[10px] text-[#5a5a6a]">
          {holdMin}m {String(holdRemSec).padStart(2, '0')}s
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-4 mb-3">
        <div>
          <div className="text-[10px] text-[#5a5a6a] mb-0.5">Entry</div>
          <div className="text-sm font-mono text-white">{fmtPremium4(entryPremium)}</div>
        </div>
        <div>
          <div className="text-[10px] text-[#5a5a6a] mb-0.5">Current</div>
          <div className="text-sm font-mono text-white">{fmtPremium4(currentPremium)}</div>
        </div>
      </div>
      
      <div className="flex items-center justify-between pt-2 border-t border-[rgba(255,255,255,0.05)]">
        <div>
          <span className="text-[10px] text-[#5a5a6a]">P&L: </span>
          <span className={cn(
            'text-sm font-mono font-bold',
            (pnlPct ?? 0) >= 0 ? 'text-[#00ff88]' : 'text-[#ff4757]'
          )}>
            {fmtPct(pnlPct)}
          </span>
        </div>
        {peakPct != null && (
          <div>
            <span className="text-[10px] text-[#5a5a6a]">Peak: </span>
            <span className="text-xs font-mono text-[#00ff88]">
              +{peakPct.toFixed(1)}%
            </span>
          </div>
        )}
      </div>
      
      {phase === 1 && (
        <div className="mt-2 text-[10px] text-[#ffb800]">
          Phase 1 (hands off) — {(30 - holdSec)}s until Phase 2
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// LOGO HEADER
// ═══════════════════════════════════════════════════════════════

function LogoHeader() {
  return (
    <div className="flex items-center justify-between mb-6 pb-4 border-b border-[rgba(255,255,255,0.05)]">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[#00ff88]/20 to-[#00d2ff]/20 border border-[#00ff88]/30">
          <span className="text-lg font-bold text-[#00ff88]">α</span>
        </div>
        <div>
          <h1 className="text-sm font-bold uppercase tracking-wider text-white">
            BB SQUEEZE
          </h1>
          <p className="text-[10px] text-[#5a5a6a]">
            Buy Cheap Premium | Hold Breakout
          </p>
        </div>
      </div>
      <div className="text-[10px] text-[#5a5a6a] font-mono">
        v0.12.2
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT — BBOptionsPanel
// ═══════════════════════════════════════════════════════════════

export function BBOptionsPanel({ asset, state, openTrade, recentEvents, botStatus }: BBOptionsPanelProps) {
  // Inject styles
  useEffect(() => { ensureStyles(); }, []);
  
  // Determine scan health
  const dataAge = state?.updated_at 
    ? Date.now() - new Date(state.updated_at).getTime() 
    : Infinity;
  const status: 'LIVE' | 'STALE' | 'DEAD' = dataAge < 45000 ? 'LIVE' : dataAge < 90000 ? 'STALE' : 'DEAD';
  
  // Extract position data
  const hasPosition = state?.position_side != null || openTrade != null;
  const positionSide = state?.position_side ?? (openTrade?.pair?.endsWith('-C') ? 'call' : 'put');
  const positionStrike = state?.position_strike ?? null;
  const entryPremium = state?.entry_premium ?? openTrade?.entry_price ?? null;
  const currentPremium = state?.current_premium ?? openTrade?.current_price ?? null;
  const pnlPct = state?.pnl_pct ?? openTrade?.current_pnl ?? null;
  const pnlUsd = state?.pnl_usd ?? null;
  const highestPremium = state?.highest_premium ?? null;
  const trailingActive = state?.trailing_active ?? openTrade?.position_state === 'trailing';
  const openedAt = openTrade?.opened_at ?? null;
  
  // Extract squeeze data
  const signalsPanel = state?.signals_panel;
  const bbWidth = signalsPanel?.bb_width_pct ?? state?.bb_width_pct ?? null;
  const bbWidthMax = signalsPanel?.bb_width_threshold ?? state?.bb_width_threshold ?? null;
  const kcContainsBB = signalsPanel?.squeeze_status === 'ACTIVE' && bbWidth != null && bbWidthMax != null && bbWidth < bbWidthMax;
  const isSqueezeActive = signalsPanel?.squeeze_status === 'ACTIVE' || state?.squeeze_active === true;
  const bbPosition = signalsPanel?.bb_position ?? state?.bb_position ?? null;
  const directionBias = (signalsPanel?.direction_bias ?? state?.direction_bias ?? 'NEUTRAL') as 'LONG' | 'SHORT' | 'NEUTRAL';
  const confidence = 0.75; // TODO: Add confidence to backend
  
  // Premium data
  const premiumAsk = signalsPanel?.premium_current_ask ?? state?.premium_current_ask ?? null;
  const cheapThreshold = signalsPanel?.premium_cheap_threshold ?? state?.premium_cheap_threshold ?? null;
  // Estimate min/max from history (backend should provide these)
  const minPremium = cheapThreshold != null ? cheapThreshold * 0.8 : premiumAsk != null ? premiumAsk * 0.7 : null;
  const maxPremium = premiumAsk != null ? premiumAsk * 1.5 : null;
  const isCheap = premiumAsk != null && cheapThreshold != null && premiumAsk <= cheapThreshold;
  
  // Last exit data
  const lastExitType = state?.last_exit_type ?? null;
  const lastExitPnl = state?.last_exit_pnl_usd ?? null;
  const lastExitPnlPct = state?.last_exit_pnl_pct ?? null;
  
  // Order status (derive from bot_state)
  const botState = state?.bot_state ?? 'scanning';
  let orderStatus: 'IDLE' | 'PENDING_FILL' | 'FILLED' | null = 'IDLE';
  if (botState.includes('squeeze:placing_order') || botState.includes('filling')) {
    orderStatus = 'PENDING_FILL';
  } else if (hasPosition) {
    orderStatus = 'FILLED';
  }
  
  // Selected side (from target or position)
  const targetStrike = state?.target_strike ?? null;
  const selectedSide: 'CALL' | 'PUT' | null = hasPosition 
    ? (positionSide === 'call' ? 'CALL' : 'PUT')
    : directionBias === 'LONG' 
      ? 'CALL' 
      : directionBias === 'SHORT' 
        ? 'PUT' 
        : null;
  
  return (
    <div 
      className="rounded-2xl p-5 border"
      style={{ 
        background: COLORS.card,
        borderColor: COLORS.border,
        backdropFilter: 'blur(20px)',
      }}
    >
      <AssetHeader 
        name={asset} 
        price={state?.spot_price ?? null} 
        balance={state?.balance ?? null}
        status={status}
      />
      
      {hasPosition ? (
        <PositionCard
          side={positionSide}
          strike={positionStrike}
          entryPremium={entryPremium}
          currentPremium={currentPremium}
          pnlPct={pnlPct}
          pnlUsd={pnlUsd}
          highestPremium={highestPremium}
          trailingActive={trailingActive}
          openedAt={openedAt}
        />
      ) : (
        <>
          <SqueezeVisualizer
            bbWidth={bbWidth}
            bbWidthMax={bbWidthMax}
            kcContainsBB={kcContainsBB}
            isActive={isSqueezeActive}
          />
          
          <PremiumRange
            min={minPremium}
            max={maxPremium}
            current={premiumAsk}
            threshold={cheapThreshold}
            isCheap={isCheap}
          />
          
          <DirectionBias
            bbPosition={bbPosition}
            bias={directionBias}
            confidence={confidence}
          />
          
          <PremiumGrid
            callPremium={state?.call_premium ?? null}
            putPremium={state?.put_premium ?? null}
            selectedSide={selectedSide}
            orderStatus={orderStatus}
            fillTimer={null} // TODO: Add fill timer to backend
          />
        </>
      )}
      
      <LastExit
        exitType={lastExitType}
        pnl={lastExitPnl}
        pnlPct={lastExitPnlPct}
      />
    </div>
  );
}
