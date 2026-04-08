'use client';

import { useMemo, useEffect, useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn } from '@/lib/utils';
import type { OptionsState } from '@/lib/types';

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
    const id = setInterval(update, 5000);
    return () => clearInterval(id);
  }, [isoTimestamp]);
  return secs;
}

function useHoldTime(isoTimestamp: string | null | undefined): string | null {
  const [display, setDisplay] = useState<string | null>(null);
  useEffect(() => {
    if (!isoTimestamp) { setDisplay(null); return; }
    const update = () => {
      const secs = Math.round((Date.now() - new Date(isoTimestamp).getTime()) / 1000);
      if (secs < 60) setDisplay(`${secs}s`);
      else if (secs < 3600) setDisplay(`${Math.floor(secs / 60)}m ${secs % 60}s`);
      else setDisplay(`${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`);
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [isoTimestamp]);
  return display;
}

// ---------------------------------------------------------------------------
// Squeeze Bar
// ---------------------------------------------------------------------------

function SqueezeBar({ bb_width_pct, bb_width_threshold, squeeze_active }: {
  bb_width_pct: number | null | undefined;
  bb_width_threshold: number | null | undefined;
  squeeze_active: boolean | null | undefined;
}) {
  if (bb_width_pct == null || bb_width_threshold == null) {
    return <div className="text-[9px] font-mono text-zinc-600 mb-2">BB: waiting...</div>;
  }

  const ratio = Math.min(bb_width_pct / bb_width_threshold, 1);
  let barColor = 'bg-[#ff1744]';
  if (ratio < 0.5) barColor = 'bg-[#00e676]';
  else if (ratio < 0.75) barColor = 'bg-[#00c853]';
  else if (ratio < 1) barColor = 'bg-[#ffd600]';

  return (
    <div className="bg-zinc-800/40 border border-zinc-800/60 rounded p-2.5 mb-2">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[9px] font-semibold text-zinc-400 uppercase tracking-wide">BB Squeeze</span>
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
        <span className="text-[8px] text-zinc-500">Width</span>
        <span className="text-[8px] font-mono text-zinc-300">
          {bb_width_pct.toFixed(2)}% / {bb_width_threshold}% thresh
        </span>
      </div>
      <div className="h-2 rounded-full bg-zinc-800 overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-500', barColor)}
          style={{ width: `${ratio * 100}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Breakout Row — shows state, velocity, and confirmation timer
// ---------------------------------------------------------------------------

function BreakoutRow({ 
  breakout_state, 
  breakout_direction, 
  secs_remaining,
  velocity_pct,
}: { 
  breakout_state: string | null | undefined;
  breakout_direction: string | null | undefined;
  secs_remaining: number | null | undefined;
  velocity_pct?: number | null;
}) {
  const state = breakout_state ?? 'NONE';
  const dir = breakout_direction;
  const isDetected = state === 'DETECTED';
  const isConfirmed = state === 'CONFIRMED' || state === 'BREAKOUT_CONFIRMED';
  const isFakeout = state === 'FAKEOUT' || state === 'BREAKOUT_FAKEOUT' || state === 'BREAKOUT_NO_FILL';

  let label: string;
  let labelColor: string;
  let rowBg: string;
  let rowBorder: string;

  if (isDetected) {
    label = dir === 'UP' ? 'DETECTED UP → CALL' : dir === 'DOWN' ? 'DETECTED DOWN → PUT' : 'DETECTED';
    labelColor = dir === 'UP' ? 'text-[#00c853]' : 'text-[#ff1744]';
    rowBg = dir === 'UP' ? 'bg-[#00c853]/10' : 'bg-[#ff1744]/10';
    rowBorder = dir === 'UP' ? 'border-[#00c853]/30' : 'border-[#ff1744]/30';
  } else if (isConfirmed) {
    label = 'CONFIRMED → ENTERING';
    labelColor = 'text-[#00c853]';
    rowBg = 'bg-[#00c853]/10';
    rowBorder = 'border-[#00c853]/30';
  } else if (isFakeout) {
    label = state === 'BREAKOUT_NO_FILL' ? 'NO FILL' : 'FAKEOUT → ABORT';
    labelColor = 'text-[#ff6d00]';
    rowBg = 'bg-[#ff6d00]/10';
    rowBorder = 'border-[#ff6d00]/30';
  } else {
    label = 'NONE';
    labelColor = 'text-zinc-600';
    rowBg = 'bg-transparent';
    rowBorder = 'border-zinc-800';
  }

  // Determine total confirmation secs based on velocity for progress bar
  const totalSecs = velocity_pct != null 
    ? (velocity_pct >= 0.3 ? 0 : velocity_pct >= 0.15 ? 20 : 60)
    : 60;

  return (
    <div className={cn('rounded border mb-2 overflow-hidden', rowBg, rowBorder)}>
      <div className="flex items-center justify-between px-2.5 py-2">
        <div className="flex items-center gap-2">
          <span className="text-[8px] text-zinc-500 uppercase tracking-wide">Breakout</span>
          <span className={cn('text-[9px] font-mono font-bold', labelColor)}>
            {(isDetected || isConfirmed) && <span className="mr-0.5">▶</span>}
            {label}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* Velocity badge */}
          {velocity_pct != null && velocity_pct > 0 && (
            <span className={cn(
              'text-[8px] font-mono px-1.5 py-0.5 rounded',
              velocity_pct >= 0.3 
                ? 'bg-[#00c853]/20 text-[#00c853]' 
                : velocity_pct >= 0.15 
                  ? 'bg-[#ffd600]/20 text-[#ffd600]' 
                  : 'bg-zinc-800 text-zinc-400'
            )}>
              {velocity_pct.toFixed(2)}%
            </span>
          )}
          {/* Confirmation timer */}
          {isDetected && secs_remaining != null && totalSecs > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-16 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-1000',
                    secs_remaining <= 5 ? 'bg-[#ff1744]' : secs_remaining <= 10 ? 'bg-[#ffd600]' : dir === 'UP' ? 'bg-[#00c853]' : 'bg-[#ff1744]'
                  )}
                  style={{ width: `${(secs_remaining / totalSecs) * 100}%` }}
                />
              </div>
              <span className={cn(
                'text-[9px] font-mono font-bold tabular-nums w-6 text-right',
                secs_remaining <= 10 ? 'text-[#ffd600] animate-pulse' : 'text-zinc-300'
              )}>
                {secs_remaining}s
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Premium Row — ATM call/put ask with strike being watched
// ---------------------------------------------------------------------------

function PremiumRow({ 
  call_ask, 
  put_ask, 
  threshold,
  atm_strike,
}: { 
  call_ask: number | null | undefined;
  put_ask: number | null | undefined;
  threshold: number | null | undefined;
  atm_strike: number | null | undefined;
}) {
  const callCheap = call_ask != null && call_ask > 0 && threshold != null && call_ask <= threshold;
  const putCheap  = put_ask  != null && put_ask  > 0 && threshold != null && put_ask  <= threshold;

  return (
    <div className="bg-zinc-800/40 border border-zinc-800/60 rounded p-2.5 mb-2">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-semibold text-zinc-400 uppercase tracking-wide">ATM Premiums</span>
          {atm_strike != null && atm_strike > 0 && (
            <span className="text-[9px] font-mono text-amber-400">
              Strike: ${atm_strike.toLocaleString()}
            </span>
          )}
        </div>
        {threshold != null && threshold > 0 && (
          <span className="text-[8px] font-mono text-zinc-500">
            cheap ≤ {fmtPrem(threshold)}
          </span>
        )}
      </div>
      <div className="flex gap-4">
        <div className="flex-1">
          <div className="text-[7px] text-[#00c853]/60 uppercase mb-0.5">Call ask</div>
          <div className="flex items-baseline gap-1">
            <span className={cn('text-[14px] font-mono font-semibold', callCheap ? 'text-[#00c853]' : 'text-zinc-200')}>
              {fmtPrem(call_ask)}
            </span>
            {callCheap && (
              <span className="text-[7px] font-mono text-[#00c853] bg-[#00c853]/10 px-1 rounded">CHEAP</span>
            )}
          </div>
        </div>
        <div className="flex-1">
          <div className="text-[7px] text-[#ff1744]/60 uppercase mb-0.5">Put ask</div>
          <div className="flex items-baseline gap-1">
            <span className={cn('text-[14px] font-mono font-semibold', putCheap ? 'text-[#00c853]' : 'text-zinc-200')}>
              {fmtPrem(put_ask)}
            </span>
            {putCheap && (
              <span className="text-[7px] font-mono text-[#00c853] bg-[#00c853]/10 px-1 rounded">CHEAP</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Position Panel — shows when in_position
// ---------------------------------------------------------------------------

function PositionPanel({ state }: { state: OptionsState }) {
  const holdTime = useHoldTime(state.position_opened_at);

  if (!state.position_side) return null;

  const isCall = state.position_side === 'call';
  const pnlPct = state.pnl_pct ?? null;
  const pnlPositive = pnlPct != null && pnlPct >= 0;
  const accentColor = isCall ? '#00c853' : '#ff1744';
  const pnlColor = pnlPct == null ? 'text-zinc-500' : pnlPositive ? 'text-[#00c853]' : 'text-[#ff1744]';

  return (
    <div
      className="rounded border p-2.5 mb-2"
      style={{
        backgroundColor: `${accentColor}0d`,
        borderColor: `${accentColor}30`,
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ backgroundColor: accentColor }}
          />
          <span className="text-[9px] font-semibold text-white uppercase tracking-wide">
            Position Open: {state.position_side.toUpperCase()}
          </span>
        </div>
        <span className="text-[9px] font-mono" style={{ color: accentColor }}>
          ${(state.position_strike ?? 0).toLocaleString()}
        </span>
      </div>

      {/* Entry / Current / P&L grid */}
      <div className="grid grid-cols-3 gap-x-2 text-[8px] mb-1.5">
        <div>
          <div className="text-zinc-600 mb-0.5">Entry</div>
          <div className="font-mono text-zinc-400">{fmtPrem(state.entry_premium)}</div>
        </div>
        <div>
          <div className="text-zinc-600 mb-0.5">Current</div>
          <div className="font-mono text-zinc-200">{fmtPrem(state.current_premium)}</div>
        </div>
        <div>
          <div className="text-zinc-600 mb-0.5">P&L</div>
          <div className={cn('font-mono font-semibold', pnlColor)}>
            {pnlPct != null
              ? `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%`
              : '—'}
          </div>
        </div>
      </div>

      {/* Hold time + USD P&L + trailing badge */}
      <div className="flex items-center justify-between text-[8px]">
        <span className="text-zinc-600">
          Hold: <span className="text-zinc-400 font-mono">{holdTime ?? '—'}</span>
        </span>
        <div className="flex items-center gap-2">
          {state.pnl_usd != null && (
            <span className={cn('font-mono', pnlColor)}>
              {state.pnl_usd >= 0 ? '+' : ''}${state.pnl_usd.toFixed(2)}
            </span>
          )}
          {state.trailing_active && (
            <span className="px-1.5 py-0.5 rounded text-[7px] font-mono bg-[#7c4dff]/20 text-[#7c4dff] border border-[#7c4dff]/30">
              TRAIL
            </span>
          )}
        </div>
      </div>
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
// Chain Card (one per asset)
// ---------------------------------------------------------------------------

function ChainCard({ asset, state }: { asset: string; state: OptionsState | null }) {
  const scanSecsAgo = useSecondsAgo(state?.updated_at);
  const hoursRemaining = fmtHoursRemaining(state?.expiry);

  // Debug: Log options_state for BTC to diagnose premium value issue
  if (asset === 'BTC' && state) {
    console.log('[BB Squeeze Debug] BTC options_state:', {
      pair: state.pair,
      call_premium: state.call_premium,
      put_premium: state.put_premium,
      atm_strike: state.atm_strike,
      spot_price: state.spot_price,
      updated_at: state.updated_at,
    });
  }

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

  return (
    <div className="bg-zinc-900/40 border border-zinc-800/50 rounded-lg p-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{asset}</span>
          <span className="text-[10px] font-mono text-zinc-500">{fmtSpot(state.spot_price)}</span>
          <span className={cn(
            'px-1.5 py-0.5 rounded text-[8px] font-mono font-bold uppercase border',
            inPosition
              ? 'bg-[#7c4dff]/15 text-[#7c4dff] border-[#7c4dff]/30'
              : 'bg-zinc-800/50 text-zinc-500 border-zinc-700'
          )}>
            {inPosition ? 'POSITION OPEN' : 'MONITORING'}
          </span>
        </div>
        <div className="text-right">
          <div className="flex items-center gap-2 justify-end">
            {hoursRemaining && (
              <span className="text-[9px] font-mono text-zinc-400">
                Exp: {hoursRemaining}
              </span>
            )}
            <span className="text-[9px] font-mono text-zinc-600 truncate max-w-[150px]">
              {state.expiry_label ?? '—'}
            </span>
          </div>
          {scanSecsAgo != null && (
            <div className="text-[8px] font-mono text-zinc-700">
              scan {scanSecsAgo < 60 ? `${scanSecsAgo}s` : `${Math.round(scanSecsAgo / 60)}m`} ago
            </div>
          )}
        </div>
      </div>

      {/* Position panel (only when open) */}
      <PositionPanel state={state} />

      {/* BB Squeeze compression bar */}
      <SqueezeBar
        bb_width_pct={state.bb_width_pct}
        bb_width_threshold={state.bb_width_threshold}
        squeeze_active={state.squeeze_active}
      />

      {/* Breakout state with velocity and timer */}
      <BreakoutRow
        breakout_state={state.breakout_state}
        breakout_direction={state.breakout_direction}
        secs_remaining={state.breakout_confirmation_secs_remaining}
        velocity_pct={state.breakout_velocity_pct}
      />

      {/* ATM call/put ask with strike being watched */}
      <PremiumRow
        call_ask={state.call_premium}
        put_ask={state.put_premium}
        threshold={state.premium_cheap_threshold}
        atm_strike={state.atm_strike}
      />

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
  const { optionsState } = useSupabase();

  const pairData = useMemo(() => {
    return OPTIONS_ASSETS.map(asset => {
      const pair  = `${asset}/USD:USD`;
      const state = optionsState.find(s => s.pair === pair) ?? null;
      return { asset, state };
    });
  }, [optionsState]);

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3 md:p-5">
      <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-4">
        Options Chain
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {pairData.map(pd => (
          <ChainCard key={pd.asset} asset={pd.asset} state={pd.state} />
        ))}
      </div>
    </div>
  );
}
