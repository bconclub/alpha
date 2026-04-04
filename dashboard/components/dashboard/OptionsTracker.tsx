'use client';

import { useMemo, useState, useEffect, useRef, useCallback } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { formatShortDate, cn } from '@/lib/utils';
import { BBOptionsPanel } from './BBOptionsPanel';
import type { OptionsState, ActivityLogRow, OpenPosition, BotStatus } from '@/lib/types';

// ── Constants ────────────────────────────────────────────────
const OPTIONS_ASSETS = ['BTC', 'ETH'] as const;
const STALE_WARN_MS = 45_000;   // yellow after 45s
const STALE_DEAD_MS = 90_000;   // red after 90s

// ── CSS-in-JS keyframes (injected once) ─────────────────────
const STYLE_ID = '__opts-tracker-pulse';
function ensureStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    @keyframes optsPulse {
      0%   { opacity: 1; transform: scale(1); }
      50%  { opacity: 0.6; transform: scale(1.15); }
      100% { opacity: 1; transform: scale(1); }
    }
    .opts-pulse-green { animation: optsPulse 2s infinite; }
    @keyframes optsFlash {
      0%   { opacity: 1; }
      50%  { opacity: 0.3; }
      100% { opacity: 1; }
    }
    .opts-flash { animation: optsFlash 0.4s ease-in-out 3; }
    @keyframes optsBarPass {
      0%   { box-shadow: 0 0 0 rgba(0,200,83,0); }
      50%  { box-shadow: 0 0 12px rgba(0,200,83,0.6); }
      100% { box-shadow: 0 0 0 rgba(0,200,83,0); }
    }
    .opts-bar-pass { animation: optsBarPass 1s ease-in-out 2; }
    @keyframes optsRegimeFlash {
      0%   { opacity: 0.4; transform: scale(0.95); }
      50%  { opacity: 1; transform: scale(1.05); }
      100% { opacity: 1; transform: scale(1); }
    }
    .opts-regime-flash { animation: optsRegimeFlash 0.5s ease-out; }
  `;
  document.head.appendChild(style);
}

// ── Helpers ──────────────────────────────────────────────────

function extractBaseAsset(pair: string): string {
  if (pair.includes('/')) return pair.split('/')[0];
  return pair.replace(/USD.*$/, '');
}

function fmtPrem(v: number | null): string {
  if (v == null) return '\u2014';
  return `$${v.toFixed(4)}`;
}

function fmtSpot(v: number | null): string {
  if (v == null) return '\u2014';
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function fmtStrike(v: number | null): string {
  if (v == null) return '\u2014';
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function ageMs(updatedAt: string | null): number {
  if (!updatedAt) return Infinity;
  return Date.now() - new Date(updatedAt).getTime();
}

const OPTION_SYMBOL_RE = /\d{6}-\d+-[CP]/;

// ── Scan staleness ──────────────────────────────────────────

type ScanHealth = 'alive' | 'stale' | 'dead';

function getScanHealth(updatedAt: string | null): ScanHealth {
  const age = ageMs(updatedAt);
  if (age < STALE_WARN_MS) return 'alive';
  if (age < STALE_DEAD_MS) return 'stale';
  return 'dead';
}

const HEALTH_DOT: Record<ScanHealth, string> = {
  alive: 'bg-[#00c853] opts-pulse-green',
  stale: 'bg-[#ffd600]',
  dead: 'bg-[#ff1744]',
};

// ── Regime helpers ──────────────────────────────────────────

function regimeColor(regime: string | null | undefined): string {
  if (!regime) return 'bg-zinc-800 text-zinc-400 border-zinc-700';
  const r = regime.toUpperCase();
  if (r.includes('TRENDING')) return 'bg-[#00c853]/15 text-[#00c853] border-[#00c853]/30';
  if (r.includes('SIDEWAYS')) return 'bg-[#ffd600]/15 text-[#ffd600] border-[#ffd600]/30';
  if (r.includes('CHOPPY')) return 'bg-[#ff1744]/15 text-[#ff1744] border-[#ff1744]/30';
  return 'bg-zinc-800 text-zinc-400 border-zinc-700';
}

// ── Bot state parser ────────────────────────────────────────

function parseBotState(botState: string | null | undefined): {
  label: string;
  color: string;
  isBlocked: boolean;
  isReady: boolean;
  blockReason?: string;
  cooldownCandles?: { current: number; needed: number } | null;
} {
  if (!botState || botState === 'scanning') {
    return { label: 'Scanning...', color: 'text-zinc-500', isBlocked: false, isReady: false };
  }
  if (botState === 'ready') {
    return { label: 'CANDLE PASS \u2014 Entering', color: 'text-[#00c853]', isBlocked: false, isReady: true };
  }
  if (botState === 'in_position') {
    return { label: 'In Position', color: 'text-[#7c4dff]', isBlocked: false, isReady: false };
  }
  if (botState.startsWith('blocked:')) {
    const parts = botState.replace('blocked:', '').split(':');
    const reason = parts[0].replace(/_/g, ' ');
    const timer = parts[1] ?? null;
    const label = timer ? `${reason} (${timer})` : reason;

    // Parse cooldown candle info: "trade_cooldown:0/3"
    let cooldownCandles: { current: number; needed: number } | null = null;
    if (timer && timer.includes('/')) {
      const [cur, tot] = timer.split('/').map(Number);
      if (!isNaN(cur) && !isNaN(tot)) cooldownCandles = { current: cur, needed: tot };
    }

    return { label, color: 'text-[#ff1744]', isBlocked: true, isReady: false, blockReason: reason, cooldownCandles };
  }
  return { label: botState.replace(/_/g, ' '), color: 'text-zinc-400', isBlocked: false, isReady: false };
}

// ── Merged state per asset ──────────────────────────────────

interface MergedPairState {
  asset: string;
  pair: string;
  state: OptionsState | null;
  recentEvents: ActivityLogRow[];
  openTrade: OpenPosition | null;
}

// ══════════════════════════════════════════════════════════════
// useLiveTick — 1-second timer for all live counters
// ══════════════════════════════════════════════════════════════

function useLiveTick(intervalMs = 1000) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return tick;
}

// ══════════════════════════════════════════════════════════════
// 1. ScanPulse — pulsing dot + "Xs ago" counter
// ══════════════════════════════════════════════════════════════

function ScanPulse({ updatedAt }: { updatedAt: string | null }) {
  useLiveTick();
  const health = getScanHealth(updatedAt);
  const ageSec = updatedAt ? Math.floor(ageMs(updatedAt) / 1000) : null;

  return (
    <span className="flex items-center gap-1.5">
      <span className={cn('w-2.5 h-2.5 rounded-full shrink-0', HEALTH_DOT[health])} />
      <span className="text-[9px] font-mono text-zinc-500">
        {ageSec != null ? `${ageSec}s ago` : 'no data'}
      </span>
    </span>
  );
}

// ══════════════════════════════════════════════════════════════
// 2. BBSqueezeSignalsPanel — BB Squeeze visualization
// ══════════════════════════════════════════════════════════════

function BBSqueezeSignalsPanel({ signals }: { signals: import('@/lib/types').SignalsPanel | null | undefined }) {
  if (!signals) return null;

  const {
    bb_width_pct,
    bb_width_threshold,
    squeeze_status,
    bb_position,
    direction_bias,
    premium_current_ask,
    premium_cheap_threshold,
    last_action,
    squeeze_duration_candles,
  } = signals;

  const isSqueezeActive = squeeze_status === 'ACTIVE';
  const widthRatio = Math.min((bb_width_pct / bb_width_threshold) * 100, 100);
  
  // Determine color based on how tight the squeeze is
  let widthColor = 'bg-[#ff1744]';  // Wide/red
  if (bb_width_pct < bb_width_threshold * 0.5) widthColor = 'bg-[#00e676]';  // Very tight
  else if (bb_width_pct < bb_width_threshold * 0.75) widthColor = 'bg-[#00c853]';  // Tight
  else if (bb_width_pct < bb_width_threshold) widthColor = 'bg-[#ffd600]';  // Getting tight

  // BB position indicator (0 = lower band, 1 = upper band)
  const positionPct = Math.max(0, Math.min(100, bb_position * 100));
  
  // Direction bias colors
  const biasColor = direction_bias === 'CALL' 
    ? 'text-[#00c853]' 
    : direction_bias === 'PUT' 
      ? 'text-[#ff1744]' 
      : 'text-zinc-400';
  const biasBg = direction_bias === 'CALL' 
    ? 'bg-[#00c853]/15 border-[#00c853]/30' 
    : direction_bias === 'PUT' 
      ? 'bg-[#ff1744]/15 border-[#ff1744]/30' 
      : 'bg-zinc-800/50 border-zinc-700';

  // Last action color
  const actionColor = last_action === 'SQUEEZE_FILL' 
    ? 'text-[#00c853]' 
    : last_action === 'SQUEEZE_NO_FILL' 
      ? 'text-[#ff1744]' 
      : 'text-zinc-500';

  return (
    <div className="bg-zinc-800/40 border border-zinc-800/60 rounded p-2.5 mb-2.5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[9px] font-semibold text-zinc-400 uppercase tracking-wide">BB Squeeze</span>
        <span className={cn(
          'px-1.5 py-0.5 rounded text-[8px] font-mono font-bold uppercase border',
          isSqueezeActive 
            ? 'bg-[#00c853]/15 text-[#00c853] border-[#00c853]/30' 
            : 'bg-zinc-800 text-zinc-500 border-zinc-700'
        )}>
          {squeeze_status}
        </span>
      </div>

      {/* BB Width % with threshold bar */}
      <div className="mb-2.5">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[8px] text-zinc-500">BB Width</span>
          <span className="text-[8px] font-mono text-zinc-300">{bb_width_pct.toFixed(2)}% / {bb_width_threshold}% threshold</span>
        </div>
        <div className="relative h-2 rounded-full bg-zinc-800 overflow-hidden">
          <div
            className={cn('absolute inset-y-0 left-0 rounded-full transition-all duration-500', widthColor)}
            style={{ width: `${widthRatio}%` }}
          />
          {/* Threshold marker */}
          <div 
            className="absolute inset-y-0 w-0.5 bg-white/50"
            style={{ left: `${Math.min((bb_width_threshold / bb_width_threshold) * 100, 100)}%` }}
          />
        </div>
      </div>

      {/* BB Position indicator (where price sits in bands) */}
      <div className="mb-2.5">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[8px] text-zinc-500">BB Position</span>
          <span className="text-[8px] font-mono text-zinc-300">{bb_position.toFixed(2)}</span>
        </div>
        <div className="relative h-1.5 rounded-full bg-gradient-to-r from-[#00c853]/30 via-zinc-700 to-[#ff1744]/30 overflow-hidden">
          <div 
            className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-white shadow-[0_0_4px_rgba(255,255,255,0.5)]"
            style={{ left: `${positionPct}%`, transform: `translateX(-50%) translateY(-50%)` }}
          />
        </div>
        <div className="flex justify-between text-[7px] text-zinc-600 mt-0.5">
          <span>Lower</span>
          <span>Middle</span>
          <span>Upper</span>
        </div>
      </div>

      {/* Direction Bias */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[8px] text-zinc-500">Direction Bias</span>
        <span className={cn(
          'px-2 py-0.5 rounded text-[9px] font-mono font-bold border',
          biasBg, biasColor
        )}>
          {direction_bias}
        </span>
      </div>

      {/* Premium: current ask vs cheap threshold */}
      {(premium_current_ask != null || premium_cheap_threshold != null) && (
        <div className="mb-2 p-1.5 bg-zinc-900/50 rounded">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[8px] text-zinc-500">Premium Ask</span>
            <span className="text-[9px] font-mono text-zinc-300">
              ${premium_current_ask?.toFixed(4) ?? '—'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[8px] text-zinc-500">Cheap Threshold</span>
            <span className="text-[9px] font-mono text-[#00c853]">
              ${premium_cheap_threshold?.toFixed(4) ?? '—'}
            </span>
          </div>
          {premium_current_ask != null && premium_cheap_threshold != null && (
            <div className="mt-1 text-[7px] font-mono">
              {premium_current_ask <= premium_cheap_threshold ? (
                <span className="text-[#00c853]">✓ Below threshold — cheap entry</span>
              ) : (
                <span className="text-[#ffd600]">Waiting for cheap entry...</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Squeeze duration */}
      <div className="flex items-center justify-between text-[8px] font-mono text-zinc-500 mb-1.5">
        <span>Squeeze duration</span>
        <span>{squeeze_duration_candles} candles</span>
      </div>

      {/* Last action */}
      <div className="flex items-center justify-between text-[8px]">
        <span className="text-zinc-500">Last action</span>
        <span className={cn('font-mono font-medium', actionColor)}>
          {last_action}
        </span>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// 3. PremiumTick — premium value + direction arrow + delta
// ══════════════════════════════════════════════════════════════

function PremiumTick({ label, value, colorUp, colorDown }: {
  label: string;
  value: number | null;
  colorUp: string;
  colorDown: string;
}) {
  const prevRef = useRef<{ value: number; timestamp: number } | null>(null);
  const [delta, setDelta] = useState<{ pct: number; direction: 'up' | 'down' | 'flat'; secAgo: number } | null>(null);

  useEffect(() => {
    if (value == null) return;
    const now = Date.now();
    if (prevRef.current && prevRef.current.value > 0) {
      const pct = ((value - prevRef.current.value) / prevRef.current.value) * 100;
      const secAgo = Math.floor((now - prevRef.current.timestamp) / 1000);
      setDelta({
        pct,
        direction: pct > 0.01 ? 'up' : pct < -0.01 ? 'down' : 'flat',
        secAgo: Math.max(secAgo, 1),
      });
    }
    prevRef.current = { value, timestamp: now };
  }, [value]);

  const arrowChar = delta?.direction === 'up' ? '\u2191' : delta?.direction === 'down' ? '\u2193' : '';
  const arrowColor = delta?.direction === 'up' ? colorUp : delta?.direction === 'down' ? colorDown : 'text-zinc-500';

  return (
    <div>
      <div className="text-[9px] text-zinc-500 uppercase mb-0.5">{label}</div>
      <div className="flex items-center gap-1.5">
        <span className={cn('text-[11px] font-mono font-medium', value != null && value > 0 ? 'text-zinc-200' : 'text-zinc-600')}>
          {fmtPrem(value)}
        </span>
        {delta && delta.direction !== 'flat' && (
          <span className={cn('text-[10px] font-bold', arrowColor)}>
            {arrowChar}
          </span>
        )}
      </div>
      {delta && delta.direction !== 'flat' && (
        <div className={cn('text-[8px] font-mono', arrowColor)}>
          {delta.pct >= 0 ? '+' : ''}{delta.pct.toFixed(1)}% from {delta.secAgo}s ago
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// 4. PositionLive — live ticking position state
// ══════════════════════════════════════════════════════════════

function PositionLive({
  positionSide,
  positionStrike,
  entryPremium,
  currentPremium,
  pnlPct,
  pnlUsd,
  highestPremium,
  trailingActive,
  openedAt,
  botState,
}: {
  positionSide: string | null;
  positionStrike: number | null;
  entryPremium: number | null;
  currentPremium: number | null;
  pnlPct: number | null;
  pnlUsd: number | null;
  highestPremium: number | null;
  trailingActive: boolean;
  openedAt: string | null;
  botState: string | null | undefined;
}) {
  useLiveTick();

  // Hold timer
  const holdSec = openedAt ? Math.floor((Date.now() - new Date(openedAt).getTime()) / 1000) : 0;
  const holdMin = Math.floor(holdSec / 60);
  const holdRemSec = holdSec % 60;

  // Peak P&L
  const peakPct = highestPremium != null && entryPremium != null && entryPremium > 0
    ? ((highestPremium - entryPremium) / entryPremium * 100)
    : null;

  // Ratchet floor (simplified display from bot state)
  // Phase detection: < 30s = phase 1 (hands off), >= 30s = phase 2 (active trailing)
  const phase = holdSec < 30 ? 1 : 2;
  const phaseCountdown = phase === 1 ? Math.max(30 - holdSec, 0) : null;

  return (
    <div className="bg-[#7c4dff]/5 border border-[#7c4dff]/20 rounded p-2.5 mb-2">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold text-[#7c4dff] uppercase tracking-wide">
          HOLDING {positionSide?.toUpperCase()} {fmtStrike(positionStrike)}
        </span>
        {trailingActive && (
          <span className="flex items-center gap-1 text-[9px] font-mono text-[#00c853]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00c853] animate-pulse" />
            TRAILING
          </span>
        )}
      </div>

      <div className="space-y-1 text-[9px] font-mono">
        {/* Hold timer */}
        <div className="flex items-center gap-1">
          <span className="text-zinc-600">\u251C Hold:</span>
          <span className="text-zinc-300">{holdMin}m {String(holdRemSec).padStart(2, '0')}s</span>
        </div>

        {/* P&L */}
        <div className="flex items-center gap-1">
          <span className="text-zinc-600">\u251C P&L:</span>
          <span className={cn('font-medium', (pnlPct ?? 0) >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
            {pnlUsd != null ? `$${pnlUsd >= 0 ? '+' : ''}${pnlUsd.toFixed(4)}` : '\u2014'}
            {pnlPct != null && ` (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%)`}
          </span>
        </div>

        {/* Peak */}
        {peakPct != null && (
          <div className="flex items-center gap-1">
            <span className="text-zinc-600">\u251C Peak:</span>
            <span className="text-[#00c853]">
              ${highestPremium!.toFixed(4)} (+{peakPct.toFixed(1)}%)
            </span>
          </div>
        )}

        {/* Entry premium */}
        <div className="flex items-center gap-1">
          <span className="text-zinc-600">\u251C Entry:</span>
          <span className="text-zinc-400">{fmtPrem(entryPremium)}</span>
          <span className="text-zinc-600">Now:</span>
          <span className="text-zinc-300">{currentPremium != null ? fmtPrem(currentPremium) : 'updating...'}</span>
        </div>

        {/* Phase */}
        <div className="flex items-center gap-1">
          <span className="text-zinc-600">\u251C Phase:</span>
          <span className="text-zinc-300">
            {phase} ({phase === 1 ? 'hands off' : 'active trailing'})
            {phaseCountdown != null && <span className="text-amber-400 ml-1">\u2192 Phase 2 in {phaseCountdown}s</span>}
          </span>
        </div>

        {/* Exit watching */}
        <div className="flex items-center gap-1">
          <span className="text-zinc-600">\u2514 Exit:</span>
          <span className="text-zinc-400">
            {trailingActive ? 'trailing stop active' : 'watching for momentum fade...'}
          </span>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// 5. CooldownDisplay — post-exit cooldown with candle count
// ══════════════════════════════════════════════════════════════

function CooldownDisplay({
  lastExitType,
  lastExitPnlPct,
  lastExitPnlUsd,
  cooldownCandles,
}: {
  lastExitType: string | null | undefined;
  lastExitPnlPct: number | null | undefined;
  lastExitPnlUsd: number | null | undefined;
  cooldownCandles: { current: number; needed: number } | null | undefined;
}) {
  if (!lastExitType) return null;

  return (
    <div className="text-[9px] font-mono mb-2 space-y-0.5">
      <div className="flex items-center gap-1">
        <span className="text-zinc-500">Last:</span>
        <span className="text-zinc-400">{lastExitType}</span>
        {lastExitPnlPct != null && (
          <span className={cn(lastExitPnlPct >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
            {lastExitPnlPct >= 0 ? '+' : ''}{lastExitPnlPct.toFixed(1)}%
          </span>
        )}
        {lastExitPnlUsd != null && (
          <span className="text-zinc-600">
            (${lastExitPnlUsd >= 0 ? '+' : ''}{lastExitPnlUsd.toFixed(4)})
          </span>
        )}
      </div>
      {cooldownCandles && (
        <div className="flex items-center gap-1.5">
          <span className="text-zinc-500">Cooldown:</span>
          <span className="text-amber-400">
            fresh candles needed ({cooldownCandles.current}/{cooldownCandles.needed} directional)
          </span>
          {/* Mini candle boxes showing progress */}
          <div className="flex gap-0.5">
            {Array.from({ length: cooldownCandles.needed }, (_, i) => (
              <div
                key={i}
                className={cn(
                  'w-2.5 h-2 rounded-sm',
                  i < cooldownCandles.current ? 'bg-amber-400' : 'bg-zinc-700',
                )}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// 6. RegimeBadge — flashing regime with duration
// ══════════════════════════════════════════════════════════════

function RegimeBadge({ regime, regimeSince }: {
  regime: string | null | undefined;
  regimeSince: string | null | undefined;
}) {
  useLiveTick();
  const prevRegimeRef = useRef<string | null>(null);
  const [isFlashing, setIsFlashing] = useState(false);

  useEffect(() => {
    if (regime && prevRegimeRef.current && regime !== prevRegimeRef.current) {
      setIsFlashing(true);
      const t = setTimeout(() => setIsFlashing(false), 1500);
      return () => clearTimeout(t);
    }
    prevRegimeRef.current = regime ?? null;
  }, [regime]);

  if (!regime) return null;

  const durationSec = regimeSince ? Math.floor((Date.now() - new Date(regimeSince).getTime()) / 1000) : null;
  const durationLabel = durationSec != null
    ? (durationSec >= 3600
      ? `${Math.floor(durationSec / 3600)}h ${Math.floor((durationSec % 3600) / 60)}m`
      : durationSec >= 60
        ? `${Math.floor(durationSec / 60)}m ${durationSec % 60}s`
        : `${durationSec}s`)
    : null;

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[9px] font-mono font-semibold uppercase border',
      regimeColor(regime),
      isFlashing && 'opts-regime-flash',
    )}>
      {regime.replace(/_/g, ' ')}
      {durationLabel && <span className="text-[8px] opacity-70">({durationLabel})</span>}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════
// PairCard — per-asset card with ALL live features
// ══════════════════════════════════════════════════════════════

function PairCard({ ps, botStatus }: { ps: MergedPairState; botStatus: BotStatus | null }) {
  const s = ps.state;

  // Position detection
  const positionSideSet = s?.position_side != null;
  const dataAge = ageMs(s?.updated_at ?? null);
  const hasPositionFromState = positionSideSet && dataAge < 5 * 60 * 1000;
  const hasPositionFromTrades = ps.openTrade != null;
  const hasPosition = hasPositionFromState || hasPositionFromTrades;

  // Derive position info
  const positionSide = s?.position_side ?? (
    hasPositionFromTrades
      ? (ps.openTrade!.pair.endsWith('-C') ? 'call' : ps.openTrade!.pair.endsWith('-P') ? 'put' : 'call')
      : null
  );
  const entryPremium = s?.entry_premium ?? (hasPositionFromTrades ? ps.openTrade!.entry_price : null);
  const currentPremium = s?.current_premium ?? (hasPositionFromTrades ? (ps.openTrade!.current_price ?? null) : null);
  const pnlPct = s?.pnl_pct ?? (hasPositionFromTrades ? (ps.openTrade!.current_pnl ?? null) : null);
  const pnlUsd = s?.pnl_usd ?? null;
  const positionStrike = s?.position_strike ?? null;
  const trailingActive = s?.trailing_active ?? (hasPositionFromTrades && ps.openTrade!.position_state === 'trailing');
  const highestPremium = s?.highest_premium ?? null;

  const botState = parseBotState(s?.bot_state);

  // Target strike + premium
  const targetStrike = s?.target_strike ?? null;
  let targetPremium: number | null = null;
  let targetCollateral: number | null = null;
  if (targetStrike != null) {
    const allChain = [...(s?.chain_calls ?? []), ...(s?.chain_puts ?? [])];
    const match = allChain.find(c => c.strike === targetStrike);
    if (match && match.ask > 0) {
      targetPremium = match.ask;
      targetCollateral = match.ask / 50;
    }
  }

  const displayStrike = hasPosition ? positionStrike : (targetStrike ?? s?.atm_strike ?? null);

  // Open trade opened_at for hold timer
  const openedAt = hasPositionFromTrades ? ps.openTrade!.opened_at : null;

  // Regime from botStatus
  const regime = botStatus?.market_regime ?? null;
  const regimeSince = botStatus?.regime_since ?? null;

  return (
    <div
      className={cn(
        'bg-zinc-900/40 border rounded-lg p-3',
        hasPosition ? 'border-[#7c4dff]/40' : botState.isReady ? 'border-[#00c853]/40' : 'border-zinc-800/50',
      )}
    >
      {/* ═══ HEADER with SCAN PULSE ═══ */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{ps.asset}</span>
          {s?.spot_price != null && (
            <span className="text-[10px] font-mono text-zinc-500">{fmtSpot(s.spot_price)}</span>
          )}
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-mono font-medium text-[#00d2ff] bg-[#00d2ff]/10">
            Delta
          </span>
        </div>
        <div className="flex items-center gap-2">
          {hasPosition && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-medium text-[#7c4dff] bg-[#7c4dff]/10 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#7c4dff] animate-pulse" />
              {positionSide?.toUpperCase()} OPEN
            </span>
          )}
          {/* 1. SCAN PULSE */}
          <ScanPulse updatedAt={s?.updated_at ?? null} />
        </div>
      </div>

      {/* No data state */}
      {!s ? (
        <div className="text-[10px] font-mono text-zinc-600 py-3 text-center">
          Waiting for engine data...
        </div>
      ) : (
        <>
          {/* ═══ STRIKE + EXPIRY + BALANCE ═══ */}
          <div className="flex items-center gap-3 mb-2.5 px-2 py-1.5 bg-zinc-800/40 rounded border border-zinc-800/60">
            <div className="flex items-center gap-1.5">
              <span className="text-[8px] text-zinc-500 uppercase">Strike</span>
              <span className={cn(
                'text-[11px] font-mono font-semibold',
                hasPosition ? 'text-[#7c4dff]' : targetStrike != null ? 'text-amber-400' : 'text-zinc-300',
              )}>
                {fmtStrike(displayStrike)}
              </span>
            </div>
            <div className="w-px h-3 bg-zinc-700" />
            <div className="flex items-center gap-1.5">
              <span className="text-[8px] text-zinc-500 uppercase">Exp</span>
              <span className="text-[10px] font-mono text-zinc-300 truncate max-w-[80px]">
                {s.expiry_label ?? '\u2014'}
              </span>
            </div>
            {s.balance != null && (
              <>
                <div className="w-px h-3 bg-zinc-700" />
                <div className="flex items-center gap-1.5">
                  <span className="text-[8px] text-zinc-500 uppercase">Bal</span>
                  <span className="text-[10px] font-mono text-zinc-300">
                    ${s.balance.toFixed(2)}
                  </span>
                </div>
              </>
            )}
          </div>

          {/* ═══ 7. REGIME BADGE ═══ */}
          <div className="mb-2.5">
            <RegimeBadge regime={regime} regimeSince={regimeSince} />
          </div>

          {/* ═══ BB SQUEEZE SIGNALS PANEL ═══ */}
          <BBSqueezeSignalsPanel signals={s.signals_panel} />

          {/* ═══ BOT STATE ═══ */}
          <div className={cn(
            'rounded px-2.5 py-1.5 mb-2.5 border',
            botState.isBlocked
              ? 'bg-[#ff1744]/5 border-[#ff1744]/20'
              : botState.isReady
                ? 'bg-[#00c853]/5 border-[#00c853]/20'
                : hasPosition
                  ? 'bg-[#7c4dff]/5 border-[#7c4dff]/20'
                  : 'bg-zinc-800/30 border-zinc-800/50',
          )}>
            <div className="flex items-center gap-2">
              <span className={cn(
                'w-2 h-2 rounded-full shrink-0',
                botState.isBlocked ? 'bg-[#ff1744]'
                  : botState.isReady ? 'bg-[#00c853] opts-pulse-green'
                  : hasPosition ? 'bg-[#7c4dff] animate-pulse'
                  : 'bg-zinc-600',
              )} />
              <span className={cn('text-[10px] font-mono font-medium uppercase', botState.color)}>
                {hasPosition && !botState.isBlocked
                  ? `${positionSide?.toUpperCase()} @ ${fmtStrike(positionStrike)}`
                  : botState.label}
              </span>
            </div>
          </div>

          {/* ═══ TARGET STRIKE + PREMIUM (when not in position) ═══ */}
          {!hasPosition && targetStrike != null && (
            <div className="flex flex-wrap gap-x-3 text-[9px] font-mono text-zinc-400 mb-2.5">
              <span><span className="text-zinc-600">Target </span><span className="text-amber-400">{fmtStrike(targetStrike)}</span></span>
              {targetPremium != null && (
                <span><span className="text-zinc-600">Ask </span>{fmtPrem(targetPremium)}</span>
              )}
              {targetCollateral != null && (
                <span><span className="text-zinc-600">Col </span>${targetCollateral.toFixed(2)}</span>
              )}
            </div>
          )}

          {/* ═══ 4. PREMIUMS with LIVE TICK ═══ */}
          <div className="grid grid-cols-2 gap-2 mb-2.5">
            <PremiumTick
              label="CALL Premium"
              value={s.call_premium}
              colorUp="text-[#00c853]"
              colorDown="text-[#ff1744]"
            />
            <PremiumTick
              label="PUT Premium"
              value={s.put_premium}
              colorUp="text-[#00c853]"
              colorDown="text-[#ff1744]"
            />
          </div>

          {/* ═══ 5. ACTIVE POSITION with LIVE TIMERS ═══ */}
          {hasPosition ? (
            <PositionLive
              positionSide={positionSide}
              positionStrike={positionStrike}
              entryPremium={entryPremium}
              currentPremium={currentPremium}
              pnlPct={pnlPct}
              pnlUsd={pnlUsd}
              highestPremium={highestPremium}
              trailingActive={trailingActive}
              openedAt={openedAt}
              botState={s.bot_state}
            />
          ) : (
            /* ═══ 6. COOLDOWN DISPLAY ═══ */
            <CooldownDisplay
              lastExitType={s.last_exit_type}
              lastExitPnlPct={s.last_exit_pnl_pct}
              lastExitPnlUsd={s.last_exit_pnl_usd}
              cooldownCandles={botState.cooldownCandles}
            />
          )}

          {/* ═══ MINI EVENT LOG ═══ */}
          {ps.recentEvents.length > 0 && (
            <div className="border-t border-zinc-800/50 pt-1.5 space-y-0.5">
              {ps.recentEvents.slice(0, 3).map((ev) => (
                <div key={ev.id} className="flex items-center gap-1.5">
                  <span className={cn(
                    'w-1 h-1 rounded-full shrink-0',
                    ev.event_type === 'options_entry' ? 'bg-[#7c4dff]'
                      : ev.event_type === 'options_exit' ? 'bg-[#7c4dff]/50'
                      : 'bg-zinc-700',
                  )} />
                  <span className="text-[8px] font-mono text-zinc-600 truncate">
                    {formatShortDate(ev.created_at)} {ev.event_type.replace('options_', '').toUpperCase()}
                    {ev.metadata?.pnl_pct != null && ` ${ev.metadata.pnl_pct >= 0 ? '+' : ''}${ev.metadata.pnl_pct.toFixed(1)}%`}
                    {ev.metadata?.option_type && ` ${ev.metadata.option_type.toUpperCase()}`}
                    {ev.metadata?.strike && ` $${ev.metadata.strike}`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// Main Export: OptionsTracker
// ══════════════════════════════════════════════════════════════

export function OptionsTracker() {
  const { optionsState, optionsLog, openPositions, botStatus } = useSupabase();

  // Inject pulse animations
  useEffect(() => { ensureStyles(); }, []);

  const pairStates = useMemo(() => {
    const results: MergedPairState[] = [];

    const optionTrades = new Map<string, OpenPosition>();
    for (const pos of (openPositions ?? [])) {
      if (pos.strategy === 'options_scalp' || OPTION_SYMBOL_RE.test(pos.pair)) {
        const asset = extractBaseAsset(pos.pair);
        optionTrades.set(asset, pos);
      }
    }

    for (const asset of OPTIONS_ASSETS) {
      const pair = `${asset}/USD:USD`;
      const state = optionsState.find((s) => s.pair === pair) ?? null;
      const assetEvents = optionsLog.filter((e) => extractBaseAsset(e.pair) === asset);

      results.push({
        asset,
        pair,
        state,
        recentEvents: assetEvents.slice(0, 5),
        openTrade: optionTrades.get(asset) ?? null,
      });
    }

    return results;
  }, [optionsState, optionsLog, openPositions]);

  return (
    <div className="bg-[#0a0a0f] border border-[rgba(255,255,255,0.05)] rounded-2xl p-4 md:p-6">
      {/* Logo Header */}
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

      {/* Cards Grid - Responsive */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {pairStates.map((ps) => (
          <BBOptionsPanel 
            key={ps.asset} 
            asset={ps.asset}
            state={ps.state}
            openTrade={ps.openTrade}
            recentEvents={ps.recentEvents}
            botStatus={botStatus}
          />
        ))}
      </div>
    </div>
  );
}
