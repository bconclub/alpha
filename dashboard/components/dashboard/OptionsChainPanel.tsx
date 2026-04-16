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

function getSignalConfidence(state: OptionsState): number {
  const raw =
    state.signal_strength != null
      ? state.signal_strength
      : state.bb_width_pct != null && state.bb_width_threshold != null && state.bb_width_threshold > 0
        ? Math.min(state.bb_width_pct / state.bb_width_threshold, 1)
        : 0;
  return Math.max(0, Math.min(1, raw));
}

// ---------------------------------------------------------------------------
// Signal battery gauge
// ---------------------------------------------------------------------------

function SqueezeBar({
  bb_width_pct, 
  bb_width_threshold, 
  squeeze_active,
  signal_strength 
}: {
  bb_width_pct: number | null | undefined;
  bb_width_threshold: number | null | undefined;
  squeeze_active: boolean | null | undefined;
  signal_strength?: number | null;
}) {
  const [displayPct, setDisplayPct] = useState(0);
  
  // Use signal_strength if available (0-1), otherwise calculate from bb_width
  const rawConfidence = signal_strength != null 
    ? signal_strength 
    : bb_width_pct != null && bb_width_threshold != null 
      ? Math.min(bb_width_pct / bb_width_threshold, 1) 
      : 0;
  
  // Clamp to 0-1 range
  const confidence = Math.max(0, Math.min(1, rawConfidence));
  const targetPct = Math.round(confidence * 100);
  
  // Animate the percentage number - must be called before any early return
  useEffect(() => {
    setDisplayPct(targetPct);
  }, [targetPct]);
  
  // Determine color based on confidence
  const barColor = confidence >= 0.7 ? '#22c55e' : confidence >= 0.4 ? '#eab308' : '#ef4444';
  const segmentFill = Array.from({ length: 5 }).map((_, i) => {
    const boundary = (i + 1) / 5;
    return confidence >= boundary;
  });
  const lowSignal = confidence < 0.2;

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
      <div className="flex items-center gap-2">
        <div className="flex-1 flex items-center gap-1">
          {segmentFill.map((on, idx) => (
            <div
              key={idx}
              className="h-2 flex-1 rounded-sm transition-opacity duration-300"
              style={{
                opacity: on ? 1 : 0.2,
                background:
                  idx <= 1
                    ? '#ef4444'
                    : idx === 2
                      ? '#eab308'
                      : '#22c55e',
                boxShadow: on ? `0 0 8px ${barColor}` : 'none',
              }}
            />
          ))}
        </div>
        <span className={cn(
          'text-[10px] font-mono font-bold min-w-[28px] text-right transition-colors duration-300',
          confidence >= 0.7 ? 'text-[#22c55e]' : confidence >= 0.4 ? 'text-[#eab308]' : 'text-[#ef4444]'
        )}>
          {displayPct}%
        </span>
      </div>
      {lowSignal && (
        <div className="mt-1 text-[8px] font-mono text-orange-300 uppercase tracking-wide">
          Low Signal - waiting...
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chain Table (CALLS or PUTS)
// ---------------------------------------------------------------------------

interface ChainEntry {
  strike: number;
  bid: number;
  ask: number;
}

function ChainTable({
  label,
  entries,
  targetStrike,
  affordableLimit,
  isCall,
  spotPrice,
}: {
  label: string;
  entries: ChainEntry[];
  targetStrike: number | null;
  affordableLimit: number;
  isCall: boolean;
  spotPrice: number | null;
}) {
  if (entries.length === 0) {
    return (
      <div className="text-[9px] font-mono text-zinc-600 py-1">
        {label}: No data
      </div>
    );
  }

  const textColor = isCall ? 'text-[#00c853]' : 'text-[#ff1744]';
  const dimColor  = isCall ? 'text-[#00c853]/60' : 'text-[#ff1744]/60';

  return (
    <div className="mb-2">
      <div className={cn('text-[9px] font-mono uppercase mb-1 font-medium', textColor)}>
        {label}
      </div>
      <table className="w-full text-[9px] font-mono">
        <thead>
          <tr className="text-zinc-600">
            <th className="text-left font-normal pb-0.5 pr-1">Strike</th>
            <th className="text-right font-normal pb-0.5 px-1">OTM%</th>
            <th className="text-right font-normal pb-0.5 px-1">Bid</th>
            <th className="text-right font-normal pb-0.5 px-1">Ask</th>
            <th className="text-right font-normal pb-0.5 px-1">Col@50x</th>
            <th className="text-right font-normal pb-0.5 pl-1">Sprd%</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => {
            const isTarget   = targetStrike != null && e.strike === targetStrike;
            const collateral = e.ask > 0 ? e.ask / OPTIONS_LEVERAGE : 0;
            const unaffordable = collateral > affordableLimit;
            const otmPct = spotPrice && spotPrice > 0
              ? Math.abs(e.strike - spotPrice) / spotPrice * 100
              : 0;
            const spreadPct = e.ask > 0 && e.bid > 0
              ? ((e.ask - e.bid) / e.ask) * 100
              : 0;

            return (
              <tr
                key={e.strike}
                className={cn(
                  'border-t border-zinc-800/30',
                  isTarget && 'bg-amber-500/10',
                  unaffordable && !isTarget && 'opacity-40',
                )}
              >
                <td className={cn(
                  'py-0.5 text-left pr-1 whitespace-nowrap',
                  isTarget ? 'text-amber-400 font-medium' : 'text-zinc-300',
                )}>
                  ${e.strike.toLocaleString()}
                  {isTarget && (
                    <span className="ml-1 px-1 py-px rounded text-[7px] bg-amber-500/20 text-amber-400 font-bold">
                      TARGET
                    </span>
                  )}
                </td>
                <td className="py-0.5 text-right px-1 text-zinc-500">
                  {otmPct.toFixed(1)}%
                </td>
                <td className={cn('py-0.5 text-right px-1', dimColor)}>
                  {fmtPrem(e.bid)}
                </td>
                <td className={cn('py-0.5 text-right px-1', textColor)}>
                  {fmtPrem(e.ask)}
                </td>
                <td className="py-0.5 text-right px-1 text-zinc-400">
                  ${collateral.toFixed(2)}
                </td>
                <td className={cn(
                  'py-0.5 text-right pl-1',
                  spreadPct > 20 ? 'text-[#ff1744]/60' : 'text-zinc-500',
                )}>
                  {spreadPct.toFixed(0)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
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
}: { 
  type: 'call' | 'put'; 
  premium: number | null; 
  breakout_state: string;
  balance: number | null;
  spotPrice: number | null;
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
        'bg-zinc-800/40 rounded p-2',
        isGlowing && 'animate-pulse'
      )}
      style={{
        border: '1px solid rgba(63,63,70,0.6)',
        boxShadow: isGlowing ? `0 0 12px ${glowColor}` : 'none',
        transition: 'box-shadow 0.3s ease'
      }}
    >
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
  const targetStrike   = state.target_strike ?? null;
  const affordableLimit = balance != null ? balance * 0.40 : Infinity;
  const confidence = getSignalConfidence(state);
  const lowSignal = confidence < 0.2;
  const isReady = confidence > 0.15;

  const breakoutState = state.breakout_state ?? 'NONE';
  const breakoutDirection =
    state.breakout_direction ??
    (breakoutState === 'UP' ? 'UP' : breakoutState === 'DOWN' ? 'DOWN' : null);
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
          : lowSignal
            ? 'border-amber-500/40'
            : 'border-zinc-800/50',
      )}
      style={{
        backgroundColor: cardTint,
        boxShadow: lowSignal
          ? '0 0 18px rgba(245, 158, 11, 0.16), inset 0 0 24px rgba(245, 158, 11, 0.05)'
          : undefined,
      }}
    >
      {lowSignal && (
        <div className="absolute top-2 left-2 z-10 pointer-events-none">
          <span className="px-2 py-0.5 rounded bg-amber-950/70 border border-amber-500/30 text-[9px] font-mono text-amber-300 uppercase tracking-wide">
            LOW SIGNAL - waiting...
          </span>
        </div>
      )}
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
            {isReady ? 'READY' : 'MONITORING'}
          </span>
          {hoursRemaining && (
            <span className="text-[9px] font-mono text-zinc-400">
              Exp: {hoursRemaining}
            </span>
          )}
        </div>
      </div>

      {/* 1. Signal Strength bar */}
      <SqueezeBar
        bb_width_pct={state.bb_width_pct}
        bb_width_threshold={state.bb_width_threshold}
        squeeze_active={state.squeeze_active}
        signal_strength={(state as any).signal_strength}
      />

      {/* 2. Squeeze active message */}
      {state.squeeze_active && (
        <div className="mb-2 px-2 py-1.5 bg-[#00c853]/10 border border-[#00c853]/30 rounded">
          <span className="text-[10px] font-medium text-[#00c853]">
            Squeeze active! Ready to enter.
          </span>
        </div>
      )}

      {/* 3. CALL and PUT premium boxes with glow on breakout */}
      <div className="grid grid-cols-2 gap-2 mb-2">
        <PremiumBox 
          type="call" 
          premium={state.call_premium} 
          breakout_state={breakoutState}
          balance={balance}
          spotPrice={state.spot_price}
        />
        <PremiumBox 
          type="put" 
          premium={state.put_premium} 
          breakout_state={breakoutState}
          balance={balance}
          spotPrice={state.spot_price}
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
      {state.atm_strike != null && state.atm_strike > 0 && (
        <div className="mb-2 px-2 py-1.5 bg-zinc-800/30 rounded">
          <span className="text-[9px] text-zinc-500 uppercase tracking-wide">Strike Watching</span>
          <span className="ml-2 text-[14px] font-mono font-bold text-amber-400">
            STRIKE ${state.atm_strike.toLocaleString()}
          </span>
        </div>
      )}

      {/* 7. Last scan indicator */}
      <CountdownRing secondsLeft={secondsLeft} progress={progress} />

      {/* CALLS chain */}
      <ChainTable
        label="CALLS"
        entries={state.chain_calls ?? []}
        targetStrike={targetStrike}
        affordableLimit={affordableLimit}
        isCall={true}
        spotPrice={state.spot_price}
      />

      {/* PUTS chain */}
      <ChainTable
        label="PUTS"
        entries={state.chain_puts ?? []}
        targetStrike={targetStrike}
        affordableLimit={affordableLimit}
        isCall={false}
        spotPrice={state.spot_price}
      />

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
