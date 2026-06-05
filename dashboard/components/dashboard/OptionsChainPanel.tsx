'use client';

import { useMemo, useEffect, useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn } from '@/lib/utils';
import type { OptionsState } from '@/lib/types';
import { getSupabase } from '@/lib/supabase';

const OPTIONS_ASSETS = ['BTC', 'ETH'] as const;
const OPTIONS_LEVERAGE = 50;

function fmtSpot(v: number | null): string {
  if (v == null) return '—';
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function fmtPrem(v: number | null | undefined): string {
  if (v == null || v <= 0) return '—';
  return `$${v.toFixed(2)}`;
}

function fmtHoursRemaining(expiryIso: string | null | undefined): string | null {
  if (!expiryIso) return null;
  const expiry = new Date(expiryIso).getTime();
  const now = Date.now();
  const msRemaining = expiry - now;
  if (msRemaining <= 0) return 'Expired';
  const hours = Math.floor(msRemaining / (1000 * 60 * 60));
  const mins = Math.floor((msRemaining % (1000 * 60 * 60)) / (1000 * 60));
  if (hours >= 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }
  return `${hours}h ${mins}m`;
}

function useSecondsAgo(isoTimestamp: string | null | undefined): number | null {
  const [secs, setSecs] = useState<number | null>(null);
  useEffect(() => {
    if (!isoTimestamp) { setSecs(null); return; }
    const update = () => setSecs(Math.round((Date.now() - new Date(isoTimestamp).getTime()) / 1000));
    update();
    const id = setInterval(update, 1000); // Tick every second for live counter
    return () => clearInterval(id);
  }, [isoTimestamp]);
  return secs;
}

function useCountdownProgress(
  isoTimestamp: string | null | undefined,
  windowSecs: number = 10,
): { secondsLeft: number | null; progress: number } {
  const secondsAgo = useSecondsAgo(isoTimestamp);
  if (secondsAgo == null) return { secondsLeft: null, progress: 0 };
  const clampedElapsed = Math.min(secondsAgo, windowSecs);
  return {
    secondsLeft: Math.max(0, windowSecs - clampedElapsed),
    progress: Math.max(0, 1 - clampedElapsed / windowSecs),
  };
}

/** 0–1 squeeze / signal fill: prefer BB width vs threshold when present (matches on-card numbers). */
function confidenceFromBbAndSignal(
  bb_width_pct: number | null | undefined,
  bb_width_threshold: number | null | undefined,
  signal_strength: number | null | undefined,
): number {
  if (
    bb_width_pct != null
    && bb_width_threshold != null
    && bb_width_threshold > 0
  ) {
    return Math.max(0, Math.min(1, bb_width_pct / bb_width_threshold));
  }
  if (signal_strength != null) {
    return Math.max(0, Math.min(1, signal_strength));
  }
  return 0;
}

function getSignalConfidence(state: OptionsState): number {
  return confidenceFromBbAndSignal(
    state.bb_width_pct,
    state.bb_width_threshold,
    state.signal_strength,
  );
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`;
}

function configNumber(
  config: Record<string, unknown> | null | undefined,
  key: string,
  fallback: number,
): number {
  const value = config?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

// ---------------------------------------------------------------------------
// Dual signal gauge
// ---------------------------------------------------------------------------

function DualSignalBar({
  bb_width_pct, 
  bb_width_threshold, 
  momentum_60s_pct,
  momentumThresholdPct,
  confidenceMinEntry,
  squeeze_active,
  signal_strength 
}: {
  bb_width_pct: number | null | undefined;
  bb_width_threshold: number | null | undefined;
  momentum_60s_pct: number | null | undefined;
  momentumThresholdPct: number;
  confidenceMinEntry: number;
  squeeze_active: boolean | null | undefined;
  signal_strength?: number | null;
}) {
  const [displaySqueezePct, setDisplaySqueezePct] = useState(0);
  const [displayMomentumPct, setDisplayMomentumPct] = useState(0);

  const squeezeConfidence = confidenceFromBbAndSignal(
    bb_width_pct,
    bb_width_threshold,
    signal_strength,
  );
  const momentumConfidence =
    momentum_60s_pct != null ? clamp01(Math.abs(momentum_60s_pct) / Math.max(momentumThresholdPct, 0.01)) : 0;
  const momentumEntryScore =
    momentum_60s_pct != null ? clamp01(Math.abs(momentum_60s_pct) / 0.20) * 100 : 0;
  const squeezePctRaw = Math.round(squeezeConfidence * 100);
  const squeezePct = squeeze_active ? squeezePctRaw : Math.min(99, squeezePctRaw);
  const momentumPct = Math.round(momentumEntryScore);
  const hasMomentumData = momentum_60s_pct != null && Number.isFinite(momentum_60s_pct);
  const momentumLabel = `MOMENTUM ${(momentum_60s_pct ?? 0) >= 0 ? '↑' : '↓'}`;
  const squeezeIsActive = squeeze_active === true;
  const momentumScanReady = hasMomentumData && momentumConfidence >= 1;
  const momentumEntryReady = momentumEntryScore >= confidenceMinEntry;
  
  useEffect(() => {
    setDisplaySqueezePct(squeezePct);
    setDisplayMomentumPct(momentumPct);
  }, [squeezePct, momentumPct]);
  
  const squeezeFill = Array.from({ length: 5 }).map((_, i) => {
    const boundary = (i + 1) / 5;
    return squeezeConfidence >= boundary;
  });
  const momentumFill = Array.from({ length: 5 }).map((_, i) => {
    const boundary = (i + 1) * 20;
    return momentumEntryScore >= boundary;
  });
  const lowSignal = squeezeConfidence < 0.2;
  const lowMomentum = !momentumScanReady;

  return (
    <div className="bg-zinc-800/40 border border-zinc-800/60 rounded p-2.5 mb-2">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[9px] font-semibold text-zinc-400 uppercase tracking-wide">Signal Strength</span>
        <span className={cn(
          'px-1.5 py-0.5 rounded text-[8px] font-mono font-bold uppercase border',
          squeeze_active
            ? 'bg-[#00c853]/15 text-[#00c853] border-[#00c853]/30'
            : 'bg-zinc-800 text-zinc-500 border-zinc-700'
        )}>
          {squeeze_active ? 'ACTIVE' : 'WAITING'}
        </span>
      </div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[8px] text-zinc-500">BB Width</span>
        <span className="text-[8px] font-mono text-zinc-300">
          {bb_width_pct?.toFixed(2) ?? '--'}% / {bb_width_threshold ?? '--'}% thresh
        </span>
      </div>
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[8px] font-semibold text-zinc-400 uppercase tracking-wide">SQUEEZE</span>
          <span className={cn(
            'text-[10px] font-mono font-bold min-w-[28px] text-right transition-colors duration-300',
            squeezeIsActive
              ? 'text-[#22c55e]'
              : squeezeConfidence >= 0.4
                ? 'text-[#eab308]'
                : 'text-[#ef4444]'
          )}>
            {displaySqueezePct}%
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1 flex items-center gap-1">
            {squeezeFill.map((on, idx) => (
              <div
                key={idx}
                className="h-2 flex-1 rounded-sm transition-opacity duration-300"
                style={{
                  opacity: on ? 1 : 0.2,
                  background:
                    squeezeIsActive
                      ? '#22c55e'
                      : idx <= 1
                        ? '#ef4444'
                        : idx === 2
                          ? '#eab308'
                          : '#f59e0b',
                }}
              />
            ))}
          </div>
        </div>
      </div>
      <div>
        <div className="flex items-center justify-between mb-1">
          <span
            className="text-[8px] font-semibold uppercase tracking-wide"
            style={{ color: lowMomentum ? '#71717a' : '#2196f3' }}
          >
            {momentumLabel}
          </span>
          <span
            className="text-[10px] font-mono font-bold min-w-[28px] text-right transition-colors duration-300"
            style={{ color: lowMomentum ? '#71717a' : '#2196f3' }}
          >
            {hasMomentumData ? `${displayMomentumPct}` : '--'}
          </span>
        </div>
        <div className="mb-1 text-[8px] font-mono text-right" style={{ color: hasMomentumData ? '#93c5fd' : '#71717a' }}>
          {hasMomentumData
            ? `${fmtPct(momentum_60s_pct)} · score ${displayMomentumPct}/${confidenceMinEntry.toFixed(0)}`
            : 'NO DATA'}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1 flex items-center gap-1">
            {momentumFill.map((on, idx) => (
              <div
                key={idx}
                className="h-2 flex-1 rounded-sm transition-opacity duration-300"
                style={{
                  opacity: lowMomentum ? (on ? 0.45 : 0.15) : on ? 1 : 0.2,
                  background: '#2196f3',
                }}
              />
            ))}
          </div>
        </div>
      </div>
      {lowMomentum && (
        <div className="mt-1 text-[8px] font-mono text-zinc-500 uppercase tracking-wide">
          Momentum below scan floor
        </div>
      )}
      {momentumScanReady && !momentumEntryReady && (
        <div className="mt-1 text-[8px] font-mono text-amber-300 uppercase tracking-wide">
          Momentum score below entry floor
        </div>
      )}
      {lowSignal && (
        <div className="mt-1 text-[8px] font-mono text-orange-300 uppercase tracking-wide">
          Waiting for market compression...
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SignalDetails — surfaces GPFC #62/#63/#67 fields from signals_panel
// ---------------------------------------------------------------------------

const REGIME_STYLE: Record<string, { color: string; bg: string; border: string; label: string }> = {
  TRENDING_UP:   { color: '#22c55e', bg: 'rgba(34,197,94,0.12)',  border: 'rgba(34,197,94,0.35)',  label: 'TRENDING ↑' },
  TRENDING_DOWN: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.35)',  label: 'TRENDING ↓' },
  CHOPPY:        { color: '#eab308', bg: 'rgba(234,179,8,0.12)',  border: 'rgba(234,179,8,0.35)',  label: 'CHOPPY' },
  UNKNOWN:       { color: '#71717a', bg: 'rgba(113,113,122,0.12)', border: 'rgba(113,113,122,0.35)', label: 'UNKNOWN' },
};

function SignalDetails({ state, inPosition }: { state: OptionsState; inPosition: boolean }) {
  const sp = state.signals_panel ?? null;
  if (!sp) return null;

  // Regime chip
  const regime = (sp.regime as string | undefined | null) ?? 'UNKNOWN';
  const regimeStyle = REGIME_STYLE[regime] ?? REGIME_STYLE.UNKNOWN;

  // BB / KC / ratio row
  const bbW = sp.bb_width_pct ?? null;
  const kcW = sp.kc_width_pct ?? null;
  const ratio = sp.bb_kc_width_ratio ?? (bbW != null && kcW && kcW > 0 ? bbW / kcW : null);
  const ratioColor =
    ratio == null ? '#71717a' :
    ratio < 0.5 ? '#22c55e' :          // tight squeeze
    ratio < 1.0 ? '#eab308' :          // BB approaching KC walls
    ratio <= 2.0 ? '#f97316' :         // breaking out
    '#ef4444';                         // already broken out — entry guard zone

  const freshness = sp.momentum_freshness_ratio ?? sp.momentum_acceleration_ratio ?? null;
  const freshnessColor = freshness == null ? '#71717a' : freshness >= 0.5 ? '#22c55e' : freshness >= 0.3 ? '#eab308' : '#71717a';

  // In-position telemetry
  const premVel = sp.premium_velocity_pct ?? null;
  const underVsPos = sp.underlying_vs_position_pct ?? null;
  const trailArmed = sp.trail_armed ?? false;
  const trailActivation = sp.trail_first_activation_pct ?? 4;

  return (
    <div className="bg-zinc-900/40 border border-zinc-800/50 rounded p-2 mb-2 space-y-1.5">
      {/* Regime + Freshness row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] text-zinc-500 uppercase tracking-wide">Regime</span>
          <span
            className="px-1.5 py-0.5 rounded text-[8px] font-mono font-bold uppercase border"
            style={{ color: regimeStyle.color, backgroundColor: regimeStyle.bg, borderColor: regimeStyle.border }}
          >
            {regimeStyle.label}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] text-zinc-500 uppercase tracking-wide">Freshness</span>
          <span className="text-[10px] font-mono font-bold" style={{ color: freshnessColor }}>
            {freshness != null ? freshness.toFixed(2) : '--'}
          </span>
        </div>
      </div>

      {/* BB / KC / ratio row */}
      <div className="flex items-center justify-between gap-2 text-[8px] font-mono">
        <span className="text-zinc-500 uppercase tracking-wide">BB / KC</span>
        <span className="text-zinc-300">
          {bbW != null ? `${bbW.toFixed(2)}%` : '--'} / {kcW != null ? `${kcW.toFixed(2)}%` : '--'}
        </span>
        <span className="text-zinc-500 uppercase tracking-wide">Ratio</span>
        <span className="font-bold" style={{ color: ratioColor }}>
          {ratio != null ? ratio.toFixed(2) : '--'}
        </span>
      </div>

      {/* In-position telemetry (only when a position exists) */}
      {inPosition && (
        <>
          <div className="flex items-center justify-between gap-2 text-[8px] font-mono pt-1 border-t border-zinc-800/50">
            <span className="text-zinc-500 uppercase tracking-wide">Prem Vel</span>
            <span className={cn(
              'font-bold',
              premVel == null ? 'text-zinc-500' : premVel >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]'
            )}>
              {premVel != null ? `${premVel >= 0 ? '+' : ''}${premVel.toFixed(2)}%/tick` : '--'}
            </span>
            <span className="text-zinc-500 uppercase tracking-wide">Spot</span>
            <span className={cn(
              'font-bold',
              underVsPos == null ? 'text-zinc-500' : underVsPos >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]'
            )}>
              {underVsPos != null ? `${underVsPos >= 0 ? '+' : ''}${underVsPos.toFixed(2)}%` : '--'}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2 text-[8px] font-mono">
            <span className="text-zinc-500 uppercase tracking-wide">Trail</span>
            <span
              className={cn(
                'px-1.5 py-0.5 rounded text-[8px] font-mono font-bold uppercase border',
                trailArmed
                  ? 'bg-[#22c55e]/15 text-[#22c55e] border-[#22c55e]/30'
                  : 'bg-zinc-800 text-zinc-500 border-zinc-700'
              )}
            >
              {trailArmed ? 'ARMED' : `DISARMED (peak < ${trailActivation}%)`}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

type TradeReadiness = 'active' | 'ready' | 'waiting' | 'blocked';

function TradeIntentPanel({
  state,
  entrySide,
  inPosition,
  momentumThresholdPct,
  confidenceMinEntry,
}: {
  state: OptionsState;
  entrySide: 'call' | 'put' | null;
  inPosition: boolean;
  momentumThresholdPct: number;
  confidenceMinEntry: number;
}) {
  const sp = state.signals_panel ?? null;
  const momentum = state.momentum_60s_pct ?? sp?.momentum_60s_pct ?? asNumber((state as any).momentum_60s);
  const momentumEntryScore = asNumber((sp as any)?.momentum_entry_score)
    ?? (momentum != null ? Math.max(0, Math.min(100, Math.abs(momentum) / 0.20 * 100)) : null);
  const freshness = sp?.momentum_freshness_ratio ?? sp?.momentum_acceleration_ratio ?? null;
  const bbWidth = state.bb_width_pct ?? sp?.bb_width_pct ?? null;
  const bbThreshold = state.bb_width_threshold ?? sp?.bb_width_threshold ?? null;
  const kcWidth = sp?.kc_width_pct ?? null;
  const ratio = sp?.bb_kc_width_ratio ?? (bbWidth != null && kcWidth && kcWidth > 0 ? bbWidth / kcWidth : null);
  const breakoutState = state.breakout_state ?? 'NONE';
  const squeezeActive = state.squeeze_active === true;
  const trendDirection = String(sp?.trend_direction ?? '').toUpperCase();
  const trend15m = asNumber(sp?.trend_15m_pct);
  const trend45m = asNumber(sp?.trend_45m_pct);
  const strong15m = asNumber(sp?.trend_strong_15m_pct) ?? 0.85;
  const regime15m = asNumber(sp?.trend_regime_15m_pct) ?? 0.6;
  const regime45m = asNumber(sp?.trend_regime_45m_pct) ?? 1.0;
  const trendSide = trendDirection === 'UP' ? 'call' : trendDirection === 'DOWN' ? 'put' : null;
  const strongTrend =
    trendSide != null &&
    trend15m != null &&
    (
      Math.abs(trend15m) >= strong15m ||
      (Math.abs(trend15m) >= regime15m && trend45m != null && Math.abs(trend45m) >= regime45m)
    );
  const momentumReady = momentum != null && Math.abs(momentum) >= momentumThresholdPct;
  const confidenceReady = momentumEntryScore == null || momentumEntryScore >= confidenceMinEntry;
  const ratioReady = ratio != null && ratio <= 1.0;
  const absMomentum = momentum != null ? Math.abs(momentum) : null;
  const targetSide =
    entrySide ??
    (momentum != null && Math.abs(momentum) >= momentumThresholdPct
      ? (momentum >= 0 ? 'call' : 'put')
      : trendSide);
  const trendContinuation = strongTrend && targetSide != null && trendSide === targetSide;
  const freshnessReady = freshness == null || freshness >= 0.5 || trendContinuation;
  const momentumCandidate = momentumReady && freshnessReady && confidenceReady;
  const freshnessLabel = freshness == null
    ? 'freshness unknown'
    : trendContinuation && freshness < 0.5
      ? `strong ${trendDirection.toLowerCase()} trend; continuation scan`
      : freshnessReady
      ? `freshness ${freshness.toFixed(2)} OK`
      : `freshness ${freshness.toFixed(2)} is stale`;
  const momentumLabel = momentum == null
    ? 'momentum unavailable'
    : `${fmtPct(momentum)} momentum`;
  const botState = state.bot_state ?? '';
  const blockedState = botState.startsWith('blocked:')
    ? botState.replace('blocked:', '').replace(/_/g, ' ').split(':').join(' ')
    : null;

  const blockers: string[] = [];
  if (!inPosition) {
    if (blockedState) blockers.push(blockedState);
    if (!squeezeActive && !momentumReady && !ratioReady) blockers.push('Bands are not compressed enough yet');
    if (!momentumReady) {
      blockers.push(
        absMomentum == null
          ? 'Waiting for momentum data'
          : `Momentum is ${absMomentum.toFixed(2)}%; needs ${momentumThresholdPct.toFixed(2)}%`,
      );
    }
    if (momentumReady && !confidenceReady) {
      blockers.push(`Momentum score is ${momentumEntryScore?.toFixed(0)}; needs ${confidenceMinEntry.toFixed(0)}`);
    }
    if (!freshnessReady) blockers.push('Move is stale; waiting for a fresh push');
    if (squeezeActive && (breakoutState === 'NONE' || breakoutState == null)) blockers.push('Squeeze is ready, waiting for breakout');
    if ((momentumCandidate || trendContinuation) && !squeezeActive) blockers.push('Momentum/trend passed; checking option premium, spread and turnover');
  }

  let readiness: TradeReadiness = 'waiting';
  let title = 'Watching for setup';
  let subtitle = 'No trade yet';
  let detail = `${momentumLabel} · ${freshnessLabel}`;
  if (inPosition) {
    readiness = 'active';
    title = `Managing ${state.position_side?.toUpperCase() ?? 'option'} position`;
    subtitle = `${fmtPct(state.pnl_pct)} now, premium ${fmtPrem(state.current_premium)}`;
    detail = state.highest_premium
      ? `Peak premium ${fmtPrem(state.highest_premium)}`
      : 'Exit rules are watching premium and peak';
  } else if (blockedState) {
    readiness = 'blocked';
    title = 'Option gate blocked';
    subtitle = blockedState;
  } else if (squeezeActive || momentumCandidate) {
    readiness = 'ready';
    title = targetSide ? `${targetSide.toUpperCase()} setup forming` : 'Setup forming';
    subtitle = squeezeActive ? 'Squeeze is ready, waiting for breakout' : 'Momentum passed; checking option quality';
  } else if (trendContinuation) {
    readiness = 'ready';
    title = `${targetSide?.toUpperCase() ?? 'Trend'} continuation`;
    subtitle = 'Strong trend; scanning option quality and spread';
  } else if (blockers.length > 0) {
    readiness = 'blocked';
    title = 'No trade';
    subtitle = blockers[0];
  }

  const tone = {
    active: 'border-violet-500/35 bg-violet-500/10 text-violet-200',
    ready: 'border-emerald-500/35 bg-emerald-500/10 text-emerald-200',
    waiting: 'border-zinc-700/70 bg-zinc-900/50 text-zinc-300',
    blocked: 'border-amber-500/30 bg-amber-500/10 text-amber-100',
  }[readiness];

  return (
    <div className={cn('mb-2 rounded border p-2.5', tone)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-wide">{title}</div>
          <div className="mt-0.5 text-[10px] text-zinc-300">{subtitle}</div>
          <div className="mt-1 text-[9px] text-zinc-500">{detail}</div>
        </div>
        <span className="shrink-0 rounded bg-black/20 px-2 py-1 text-[9px] font-mono font-bold uppercase">
          {readiness}
        </span>
      </div>
      {!inPosition && blockers.length > 1 && (
        <div className="mt-2 rounded bg-black/15 px-2 py-1.5 text-[9px] text-zinc-400">
          Next: {blockers.slice(1, 3).join('. ')}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Breakout Badge Component
// ---------------------------------------------------------------------------

const breakoutStyle: Record<string, React.CSSProperties> = {
  NONE: { backgroundColor: '#374151', color: '#9ca3af', border: '1px solid #4b5563', borderRadius: '4px', padding: '2px 8px', fontSize: '9px', fontFamily: 'monospace', fontWeight: 'bold', textTransform: 'uppercase' },
  DETECTED_UP: { backgroundColor: '#14532d', color: '#4ade80', border: '1px solid #22c55e', borderRadius: '4px', padding: '2px 8px', fontSize: '9px', fontFamily: 'monospace', fontWeight: 'bold', textTransform: 'uppercase', animation: 'breakout-pop 1s ease-in-out infinite' },
  DETECTED_DOWN: { backgroundColor: '#450a0a', color: '#f87171', border: '1px solid #ef4444', borderRadius: '4px', padding: '2px 8px', fontSize: '9px', fontFamily: 'monospace', fontWeight: 'bold', textTransform: 'uppercase', animation: 'breakout-pop 1s ease-in-out infinite' },
  CONFIRMED: { backgroundColor: '#14532d', color: '#22c55e', border: '1px solid #22c55e', borderRadius: '4px', padding: '2px 8px', fontSize: '9px', fontFamily: 'monospace', fontWeight: 'bold', textTransform: 'uppercase' },
  FAKEOUT: { backgroundColor: '#431407', color: '#fb923c', border: '1px solid #f97316', borderRadius: '4px', padding: '2px 8px', fontSize: '9px', fontFamily: 'monospace', fontWeight: 'bold', textTransform: 'uppercase' },
};

function BreakoutBadge({ 
  state, 
  direction, 
  velocity 
}: { 
  state: string; 
  direction: 'UP' | 'DOWN' | null | undefined; 
  velocity: number | null | undefined;
}) {
  const normalizedState = state === 'NONE' || !state ? 'NONE' :
    state === 'DETECTED_UP' || state === 'BREAKOUT_UP' || (state === 'DETECTED' && direction === 'UP') ? 'DETECTED_UP' :
    state === 'DETECTED_DOWN' || state === 'BREAKOUT_DOWN' || (state === 'DETECTED' && direction === 'DOWN') ? 'DETECTED_DOWN' :
    state === 'CONFIRMED' || state === 'BREAKOUT_CONFIRMED' ? 'CONFIRMED' :
    state === 'FAKEOUT' || state === 'BREAKOUT_FAKEOUT' ? 'FAKEOUT' : 'NONE';
  
  const style = breakoutStyle[normalizedState];
  
  // Get arrow/checkmark/X
  const icon = normalizedState === 'DETECTED_UP' ? '↑ ' :
    normalizedState === 'DETECTED_DOWN' ? '↓ ' :
    normalizedState === 'CONFIRMED' ? '✓ ' :
    normalizedState === 'FAKEOUT' ? '✗ ' : '';
  
  const label = normalizedState === 'DETECTED_UP' ? 'DETECTED UP' :
    normalizedState === 'DETECTED_DOWN' ? 'DETECTED DOWN' :
    normalizedState;
  
  return (
    <span style={style}>
      <span className="inline-flex items-center gap-1">
        <span>{icon}</span>
        <span>{label}</span>
        {velocity != null && normalizedState.startsWith('DETECTED') && (
          <span style={{ opacity: 0.8, fontSize: '8px' }}>({velocity.toFixed(2)}%)</span>
        )}
      </span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Premium Box with glow effect during breakout
// ---------------------------------------------------------------------------

function PremiumBox({ 
  type, 
  premium, 
  breakout_state,
  balance,
  spotPrice,
  isEntryTarget = false,
}: { 
  type: 'call' | 'put'; 
  premium: number | null; 
  breakout_state: string;
  balance: number | null;
  spotPrice: number | null;
  isEntryTarget?: boolean;
}) {
  const isCall = type === 'call';
  const colorClass = isCall ? 'text-[#00c853]' : 'text-[#ff1744]';
  const dimColorClass = isCall ? 'text-[#00c853]/60' : 'text-[#ff1744]/60';
  
  const isGlowing = ['DETECTED_UP', 'DETECTED_DOWN', 'CONFIRMED', 'BREAKOUT_CONFIRMED'].includes(breakout_state);
  const glowColor = breakout_state === 'DETECTED_DOWN' ? '#ef4444' : '#22c55e';
  const collateralPerContract = premium != null && premium > 0 ? premium / OPTIONS_LEVERAGE : 0;
  const estimatedContracts =
    balance != null && collateralPerContract > 0 ? Math.max(1, Math.floor((balance * 0.4) / collateralPerContract)) : 0;
  const contractMultiplier = spotPrice && spotPrice > 50000 ? 0.001 : 0.01;
  const feeRate = 0.000118;
  const estimatedFee =
    premium != null && premium > 0 && spotPrice != null && estimatedContracts > 0
      ? estimatedContracts * contractMultiplier * spotPrice * feeRate
      : 0;
  const estimatedPremiumValue =
    premium != null && premium > 0 && estimatedContracts > 0 ? premium * estimatedContracts : 0;
  const feeRatioPct = estimatedPremiumValue > 0 ? (estimatedFee / estimatedPremiumValue) * 100 : 0;
  const lowRR = feeRatioPct > 15;
  
  return (
    <div 
      className={cn(
        'rounded p-2 transition-colors duration-200',
      )}
      style={{
        border: isEntryTarget
          ? (isCall ? '2px solid rgba(34,197,94,0.95)' : '2px solid rgba(239,68,68,0.95)')
          : isGlowing
            ? `2px solid ${glowColor}99`
          : '1px solid rgba(63,63,70,0.6)',
        backgroundColor: isEntryTarget
          ? (isCall ? 'rgba(34,197,94,0.14)' : 'rgba(239,68,68,0.14)')
          : isGlowing
            ? (breakout_state === 'DETECTED_DOWN'
                ? 'rgba(239,68,68,0.08)'
                : 'rgba(34,197,94,0.08)')
          : 'rgba(39,39,42,0.4)',
        boxShadow: isEntryTarget
          ? (isCall
              ? '0 0 0 1px rgba(34,197,94,0.45), 0 0 14px rgba(34,197,94,0.25)'
              : '0 0 0 1px rgba(239,68,68,0.45), 0 0 14px rgba(239,68,68,0.25)')
          : undefined,
      }}
    >
      {isEntryTarget && (
        <div className={cn(
          'mb-1 text-[8px] font-mono font-semibold uppercase tracking-wide',
          isCall ? 'text-[#86efac]' : 'text-[#fca5a5]'
        )}>
          Entry Target
        </div>
      )}
      <div className={cn('text-[7px] uppercase mb-0.5', dimColorClass)}>
        {isCall ? 'Call' : 'Put'}
      </div>
      <div className={cn('text-[14px] font-mono font-semibold text-zinc-200', colorClass)}>
        {fmtPrem(premium)}
      </div>
      <div className="mt-0.5 text-[8px] font-mono text-zinc-500">
        Est fee: ${estimatedFee.toFixed(2)}
      </div>
      {lowRR && (
        <div className="text-[8px] font-mono text-orange-400 font-semibold mt-0.5">
          ⚠ LOW R/R
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Countdown ring for refresh freshness
// ---------------------------------------------------------------------------

function CountdownRing({ secondsLeft, progress }: { secondsLeft: number | null; progress: number }) {
  if (secondsLeft == null) return null;
  const radius = 10;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - progress);

  return (
    <div className="mb-3 flex items-center justify-end gap-1.5">
      <span className="text-[8px] font-mono text-zinc-500">Refresh</span>
      <div className="relative h-6 w-6">
        <svg className="h-6 w-6 -rotate-90" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r={radius} stroke="rgba(63,63,70,0.7)" strokeWidth="3" fill="transparent" />
          <circle
            cx="12"
            cy="12"
            r={radius}
            stroke="#22c55e"
            strokeWidth="3"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-500"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[8px] font-mono text-zinc-300">
          {secondsLeft}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chain Card (one per asset)
// ---------------------------------------------------------------------------

function ChainCard({
  asset,
  state,
  strategyScore,
}: {
  asset: string;
  state: OptionsState | null;
  strategyScore: number | null;
}) {
  const { secondsLeft, progress } = useCountdownProgress(state?.updated_at, 10);
  const hoursRemaining = fmtHoursRemaining(state?.expiry);

  if (!state) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800/50 rounded-lg p-3">
        <span className="text-sm font-medium text-zinc-500">{asset}</span>
        <span className="text-[9px] font-mono text-zinc-600 ml-2">No data</span>
      </div>
    );
  }

  const inPosition     = !!state.position_side;
  const balance        = state.balance ?? null;
  const strikeWatching = state.atm_strike ?? state.target_strike ?? null;
  const momentumThresholdPct = configNumber(state.entry_config, 'mb_threshold_pct', 0.06);
  const confidenceMinEntry = configNumber(state.entry_config, 'confidence_min_entry', 60);
  const confidence = getSignalConfidence(state);
  const lowSignal = confidence < 0.2;
  const isReady = inPosition || confidence > 0.15;
  // Low-signal amber border is for idle monitoring only; an active position
  // is already called out by the purple bar — avoid stacking amber on that card.
  const useLowSignalBorder = lowSignal && !inPosition;

  const breakoutState = state.breakout_state ?? 'NONE';
  const breakoutDirection =
    state.breakout_direction ??
    (breakoutState === 'UP' ? 'UP' : breakoutState === 'DOWN' ? 'DOWN' : null);
  const normalizedPositionSide = state.position_side?.toLowerCase();
  const normalizedSignalSide = state.signal_side?.toLowerCase();
  const entrySide: 'call' | 'put' | null =
    normalizedPositionSide === 'call' || normalizedPositionSide === 'put'
      ? (normalizedPositionSide as 'call' | 'put')
      : breakoutDirection === 'UP'
        ? 'call'
        : breakoutDirection === 'DOWN'
          ? 'put'
          : normalizedSignalSide === 'call' || normalizedSignalSide === 'put'
            ? (normalizedSignalSide as 'call' | 'put')
            : state.direction_bias === 'CALL'
              ? 'call'
              : state.direction_bias === 'PUT'
                ? 'put'
                : null;
  const cardTint =
    breakoutDirection === 'UP'
      ? 'rgba(0,200,83,0.04)'
      : breakoutDirection === 'DOWN'
        ? 'rgba(239,68,68,0.04)'
        : 'rgba(24,24,27,0.4)';

  return (
    <div
      className={cn(
        'relative border rounded-lg p-3 transition-all duration-300',
        isReady
          ? 'border-[#22c55e]/70 shadow-[0_0_0_1px_rgba(34,197,94,0.45)]'
          : useLowSignalBorder
            ? 'border-amber-500/40'
            : 'border-zinc-800/50',
      )}
      style={{
        backgroundColor: cardTint,
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{asset}</span>
          <span className="text-[10px] font-mono text-zinc-500">{fmtSpot(state.spot_price)}</span>
          <span className="text-[9px] font-mono text-zinc-400">
            Strategy Score: {strategyScore != null ? `${strategyScore.toFixed(0)}%` : '--'}
          </span>
        </div>
        <div className="text-right flex items-center gap-2">
          <span className={cn(
            'px-1.5 py-0.5 rounded text-[8px] font-mono font-bold border uppercase',
            isReady
              ? 'bg-[#22c55e]/15 text-[#22c55e] border-[#22c55e]/30'
              : 'bg-zinc-800 text-zinc-500 border-zinc-700',
          )}>
            {inPosition ? 'IN TRADE' : 'SCANNING'}
          </span>
          {hoursRemaining && (
            <span className="text-[9px] font-mono text-zinc-400">
              Exp: {hoursRemaining}
            </span>
          )}
        </div>
      </div>

      <TradeIntentPanel
        state={state}
        entrySide={entrySide}
        inPosition={inPosition}
        momentumThresholdPct={momentumThresholdPct}
        confidenceMinEntry={confidenceMinEntry}
      />

      {/* 1. Dual signal bar */}
      <DualSignalBar
        bb_width_pct={state.bb_width_pct}
        bb_width_threshold={state.bb_width_threshold}
        momentum_60s_pct={
          state.momentum_60s_pct
          ?? state.signals_panel?.momentum_60s_pct
          ?? (state as any).momentum_60s
          ?? (state.signals_panel as any)?.momentum_60s
          ?? null
        }
        momentumThresholdPct={momentumThresholdPct}
        confidenceMinEntry={confidenceMinEntry}
        squeeze_active={state.squeeze_active}
        signal_strength={(state as any).signal_strength}
      />

      {/* 1b. GPFC #62/#63/#67 signals — regime, BB/KC ratio, freshness, in-position telemetry */}
      <SignalDetails state={state} inPosition={inPosition} />

      {/* 2. Squeeze active message */}
      {state.squeeze_active && (
        <div className="mb-2 px-2 py-1.5 bg-[#00c853]/10 border border-[#00c853]/30 rounded">
          <span className="text-[10px] font-medium text-[#00c853]">
            Squeeze active! Ready to enter.
          </span>
        </div>
      )}

      {/* 3. CALL and PUT premium boxes with glow on breakout */}
      {entrySide && (
        <div className="mb-2 px-2 py-1 bg-zinc-800/30 rounded flex items-center justify-between">
          <span className="text-[9px] text-zinc-500 uppercase tracking-wide">Entry Side</span>
          <span className={cn(
            'text-[10px] font-mono font-bold uppercase',
            entrySide === 'call' ? 'text-[#22c55e]' : 'text-[#ef4444]'
          )}>
            {entrySide.toUpperCase()}
          </span>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2 mb-2">
        <PremiumBox 
          type="call" 
          premium={state.call_premium} 
          breakout_state={breakoutState}
          balance={balance}
          spotPrice={state.spot_price}
          isEntryTarget={entrySide === 'call'}
        />
        <PremiumBox 
          type="put" 
          premium={state.put_premium} 
          breakout_state={breakoutState}
          balance={balance}
          spotPrice={state.spot_price}
          isEntryTarget={entrySide === 'put'}
        />
      </div>

      {/* 4. Position Active bar */}
      {inPosition && (
        <div className="mb-2 px-2.5 py-2 bg-[#7c4dff]/10 border border-[#7c4dff]/30 rounded">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#7c4dff] animate-pulse" />
            <span className="text-[10px] font-medium text-[#7c4dff]">
              Position Active: {state.position_side?.toUpperCase()} ${state.position_strike?.toLocaleString()}
            </span>
          </div>
        </div>
      )}

      {/* 5. Breakout state row with animated badge */}
      <div className="flex items-center justify-between mb-2 px-2 py-1.5 bg-zinc-800/30 rounded">
        <span className="text-[9px] text-zinc-500 uppercase tracking-wide">Breakout</span>
        <BreakoutBadge 
          state={breakoutState} 
          direction={state.breakout_direction} 
          velocity={state.breakout_velocity_pct}
        />
      </div>

      {/* 6. Strike display - bold monospace, larger font */}
      {strikeWatching != null && strikeWatching > 0 && (
        <div className="mb-2 px-2 py-1.5 bg-zinc-800/30 rounded">
          <span className="text-[9px] text-zinc-500 uppercase tracking-wide">Strike Watching</span>
          <span className="ml-2 text-[14px] font-mono font-bold text-amber-400">
            STRIKE ${strikeWatching.toLocaleString()}
          </span>
        </div>
      )}

      {/* 7. Last scan indicator */}
      <CountdownRing secondsLeft={secondsLeft} progress={progress} />

      {balance != null && (
        <div className="text-[9px] font-mono text-zinc-600 mt-2 pt-1.5 border-t border-zinc-800/30 text-right">
          Delta balance: ${balance.toFixed(2)}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Panel
// ---------------------------------------------------------------------------

export function OptionsChainPanel() {
  const { optionsState, setOptionsState, trades } = useSupabase();
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  
  // Auto-refresh: poll options_state every 10s
  useEffect(() => {
    const fetchOptionsState = async () => {
      const client = getSupabase();
      if (!client) {
        console.log('[OptionsChainPanel] No Supabase client');
        return;
      }
      try {
        const res = await client.from('options_state').select('*');
        if (res.data) {
          console.log('[OptionsChainPanel] Fetched', res.data.length, 'rows');
          setOptionsState(res.data as OptionsState[]);
          setLastUpdate(new Date());
        }
        if (res.error) {
          console.error('[OptionsChainPanel] Error:', res.error);
        }
      } catch (e) { 
        console.error('[OptionsChainPanel] Exception:', e);
      }
    };
    
    // Initial fetch
    fetchOptionsState();
    
    // Poll every 10 seconds
    const intervalId = setInterval(fetchOptionsState, 10000);
    
    return () => clearInterval(intervalId);
  }, [setOptionsState]);

  const pairData = useMemo(() => {
    return OPTIONS_ASSETS.map(asset => {
      const pair  = `${asset}/USD:USD`;
      const state = optionsState.find(s => s.pair === pair) ?? null;
      return { asset, state };
    });
  }, [optionsState]);

  const todayWinRate = useMemo(() => {
    const now = new Date();
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const todaysOptionsTrades = trades.filter((t) => {
      const closedAt = t.closed_at ? new Date(t.closed_at).getTime() : null;
      const ts = t.timestamp ? new Date(t.timestamp).getTime() : null;
      const tradeTime = closedAt ?? ts;
      return (
        tradeTime != null &&
        tradeTime >= startOfDay &&
        t.status === 'closed' &&
        t.strategy.toLowerCase().includes('option')
      );
    });
    if (todaysOptionsTrades.length === 0) return null;
    const winners = todaysOptionsTrades.filter((t) => (t.pnl_pct ?? 0) > 0).length;
    return (winners / todaysOptionsTrades.length) * 100;
  }, [trades]);
  
  // Show stale data warning if no update in 30s
  const isStale = !lastUpdate || (Date.now() - lastUpdate.getTime()) > 30000;

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3 md:p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider">
          Options Chain
        </h3>
        {isStale && (
          <span style={{ 
            fontSize: '10px', 
            color: '#ef4444',
            backgroundColor: 'rgba(239,68,68,0.2)',
            padding: '2px 8px',
            borderRadius: '4px',
            fontFamily: 'monospace'
          }}>
            STALE DATA
          </span>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {pairData.map(pd => (
          <ChainCard key={pd.asset} asset={pd.asset} state={pd.state} strategyScore={todayWinRate} />
        ))}
      </div>
      <style jsx global>{`
        @keyframes breakout-pop {
          0%, 100% { transform: scale(1); box-shadow: 0 0 0 rgba(34, 197, 94, 0); }
          50% { transform: scale(1.08); box-shadow: 0 0 14px rgba(34, 197, 94, 0.35); }
        }
      `}</style>
    </div>
  );
}
