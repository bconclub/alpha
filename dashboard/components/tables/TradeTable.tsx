'use client';

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import type { Trade, Strategy, Exchange, PositionType, OptionsState } from '@/lib/types';
import {
  formatCurrency,
  formatPrice,
  formatPnL,
  formatPercentage,
  formatDate,
  formatDuration,
  cn,
  getPnLColor,
  tradesToCSV,
  getExchangeLabel,
  getExchangeColor,
  getPositionTypeLabel,
  getPositionTypeColor,
  formatLeverage,
  getStrategyLabel,
  getStrategyBadgeVariant,
} from '@/lib/utils';
import { Badge } from '@/components/ui/Badge';
import { ExitChip } from '@/components/ui/ExitChip';
import { SetupChip } from '@/components/ui/SetupChip';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { getSupabase } from '@/lib/supabase';
import { useLivePrices } from '@/hooks/useLivePrices';
import {
  type PositionDisplay,
  TRAIL_ACTIVATION_PCT,
  DEFAULT_SL_PCT,
  OPT_TRAIL_ACTIVATION_PCT,
  OPT_TRAIL_DISTANCE_PCT,
  getPositionState,
  StateBadge,
  PositionRangeBar,
} from '@/components/dashboard/PositionBar';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SortKey = keyof Pick<
  Trade,
  'timestamp' | 'pair' | 'side' | 'price' | 'amount' | 'strategy' | 'pnl' | 'pnl_pct' | 'status' | 'exchange' | 'position_type' | 'leverage' | 'gross_pnl'
>;

type SortDirection = 'asc' | 'desc';

type PnLFilter = 'all' | 'profit' | 'loss';

interface TradeTableProps {
  trades: Trade[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STRATEGIES: Strategy[] = ['options_scalp'];
const EXCHANGES: { label: string; value: Exchange | 'All' }[] = [
  { label: 'All', value: 'All' },
  { label: 'Bybit', value: 'bybit' },
  { label: 'Delta', value: 'delta' },
  { label: 'Kraken', value: 'kraken' },
];
const POSITION_TYPES: { label: string; value: PositionType | 'All' }[] = [
  { label: 'All', value: 'All' },
  { label: 'Spot', value: 'spot' },
  { label: 'Long', value: 'long' },
  { label: 'Short', value: 'short' },
];
const PNL_OPTIONS: { label: string; value: PnLFilter }[] = [
  { label: 'All', value: 'all' },
  { label: 'Profit', value: 'profit' },
  { label: 'Loss', value: 'loss' },
];
const TRADES_PER_PAGE = 50;

// Delta contract sizes (must match engine/alpha/trade_executor.py)
const DELTA_CONTRACT_SIZE: Record<string, number> = {
  'BTC/USD:USD': 0.001,
  'ETH/USD:USD': 0.01,
  'SOL/USD:USD': 1.0,
  'XRP/USD:USD': 1.0,
};

// Options contract multiplier by base asset (must match engine)
const OPTION_CONTRACT_MULTIPLIER: Record<string, number> = {
  BTC: 0.001,
  ETH: 0.01,
};

// ── Options helpers ──────────────────────────────────────────
/** Options symbol pattern: contains date-strike-C/P  (e.g. "260221-98000-C") */
const OPTION_SYMBOL_RE = /\d{6}-\d+-[CP]/;
function isOptionTrade(trade: Trade): boolean {
  return trade.strategy === 'options_scalp' || OPTION_SYMBOL_RE.test(trade.pair);
}

function getOptionSide(pair: string): 'CALL' | 'PUT' | null {
  if (pair.endsWith('-C')) return 'CALL';
  if (pair.endsWith('-P')) return 'PUT';
  return null;
}

/** Shorten an options pair for display: "ETH/USD:USD-260221-1960-C" → "ETH 1960C 21Feb26" */
function displayOptionPair(pair: string): string {
  // Date format in symbol is YYMMDD: 260221 = 2026-02-21
  const m = pair.match(/^(\w+)\/.*-(\d{2})(\d{2})(\d{2})-(\d+)-([CP])$/);
  if (!m) return displayPair(pair);
  const [, asset, yy, mm, dd, strike, cp] = m;
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const monthLabel = months[parseInt(mm, 10) - 1] ?? mm;
  return `${asset} ${strike}${cp} ${dd}${monthLabel}${yy}`;
}


type ColumnDef = { key: string; label: string; align?: 'right' };

const COLUMNS: ColumnDef[] = [
  // ── Frozen columns (sticky left) ──
  { key: 'id', label: '#' },
  { key: 'pair', label: 'Pair' },
  { key: 'position_type', label: 'Type' },
  { key: 'leverage', label: 'Lev', align: 'right' },
  { key: 'price', label: 'Entry', align: 'right' },
  // ── Scrollable columns ──
  { key: 'timestamp', label: 'Date' },
  { key: 'exchange', label: 'Exchange' },
  { key: 'exit_price', label: 'Exit', align: 'right' },
  { key: 'amount', label: 'Contracts', align: 'right' },
  { key: 'strategy', label: 'Strategy' },
  { key: 'setup_type', label: 'Setup' },
  { key: 'gross_pnl', label: 'Gross P&L', align: 'right' },
  { key: 'fees', label: 'Fees', align: 'right' },
  { key: 'pnl', label: 'Net P&L', align: 'right' },
  { key: 'pnl_pct', label: 'P&L %', align: 'right' },
  { key: 'hold_time', label: 'Hold Time', align: 'right' },
  { key: 'sl_price', label: 'SL', align: 'right' },
  { key: 'trail_info', label: 'Trail' },
  { key: 'peak_info', label: 'Peak', align: 'right' },
  { key: 'exit_reason', label: 'Exit' },
  { key: 'status', label: 'Status' },
];

// Frozen column sticky offsets (must match actual rendered widths)
const STICKY_COLS: Record<string, string> = {
  id: 'left-0',
  pair: 'left-[52px]',
  position_type: 'left-[152px]',
  leverage: 'left-[232px]',
  price: 'left-[292px]',
};
const LAST_STICKY_COL = 'price';

// Setup type badge colors
const SETUP_COLORS: Record<string, { bg: string; text: string }> = {
  ACCEL_ENTRY:    { bg: 'bg-amber-500/10',   text: 'text-amber-400' },
  ANTIC:          { bg: 'bg-violet-500/10',  text: 'text-violet-400' },
  VWAP_RECLAIM:   { bg: 'bg-blue-500/10',   text: 'text-blue-400' },
  RSI_OVERRIDE:   { bg: 'bg-purple-500/10',  text: 'text-purple-400' },
  MOMENTUM_BURST: { bg: 'bg-orange-500/10',  text: 'text-orange-400' },
  MOMENTUM_BURST_ENTRY: { bg: 'bg-orange-500/10', text: 'text-orange-400' },
  MEAN_REVERT:    { bg: 'bg-cyan-500/10',    text: 'text-cyan-400' },
  TREND_CONT:     { bg: 'bg-emerald-500/10', text: 'text-emerald-400' },
  BB_SQUEEZE:     { bg: 'bg-red-500/10',     text: 'text-red-400' },
  LIQ_SWEEP:      { bg: 'bg-pink-500/10',    text: 'text-pink-400' },
  FVG_FILL:       { bg: 'bg-indigo-500/10',  text: 'text-indigo-400' },
  BPRC_RELOAD:    { bg: 'bg-lime-500/10',    text: 'text-lime-400' },
  VOL_DIVERGENCE: { bg: 'bg-teal-500/10',    text: 'text-teal-400' },
  MULTI_SIGNAL:   { bg: 'bg-yellow-500/10',  text: 'text-yellow-400' },
  MIXED:          { bg: 'bg-zinc-500/10',    text: 'text-zinc-400' },
};

function getSetupLabel(setup?: string): string {
  if (!setup) return '—';
  const labels: Record<string, string> = {
    ACCEL_ENTRY: 'ACCEL',
    ANTIC: 'ANTIC',
    VWAP_RECLAIM: 'VWAP',
    RSI_OVERRIDE: 'RSI OVR',
    MOMENTUM_BURST: 'MOM BURST',
    MOMENTUM_BURST_ENTRY: 'MOM BURST',
    MEAN_REVERT: 'REVERT',
    TREND_CONT: 'TREND',
    BB_SQUEEZE: 'SQUEEZE',
    LIQ_SWEEP: 'SWEEP',
    FVG_FILL: 'FVG',
    BPRC_RELOAD: 'BPRC',
    VOL_DIVERGENCE: 'VOL DIV',
    MULTI_SIGNAL: 'MULTI',
    MIXED: 'MIXED',
  };
  return labels[setup] ?? setup;
}

function inferSetupType(trade: Trade): string | undefined {
  if (trade.setup_type && trade.setup_type.trim()) {
    const raw = trade.setup_type.trim();
    if (raw === 'MOMENTUM_BURST_ENTRY') return 'MOMENTUM_BURST_ENTRY';
    return raw;
  }
  const haystack = `${trade.reason ?? ''} ${trade.order_id ?? ''}`.toUpperCase();
  if (haystack.includes('MOMENTUM_BURST_ENTRY')) return 'MOMENTUM_BURST_ENTRY';
  if (haystack.includes('MOMENTUM_BURST')) return 'MOMENTUM_BURST';
  if (haystack.includes('BB_SQUEEZE_BREAKOUT')) return 'BB_SQUEEZE';
  if (haystack.includes('BB_SQUEEZE')) return 'BB_SQUEEZE';
  return undefined;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getStatusBadgeVariant(status: Trade['status']) {
  const map: Record<Trade['status'], 'success' | 'danger' | 'default'> = {
    open: 'success',
    closed: 'default',
    cancelled: 'danger',
  };
  return map[status];
}

function compareTrades(a: Trade, b: Trade, key: string, dir: SortDirection): number {
  let aVal: string | number = (a[key as keyof Trade] as string | number | undefined | null) ?? 0;
  let bVal: string | number = (b[key as keyof Trade] as string | number | undefined | null) ?? 0;

  if (key === 'timestamp') {
    aVal = new Date(aVal as string).getTime();
    bVal = new Date(bVal as string).getTime();
  }

  if (typeof aVal === 'string' && typeof bVal === 'string') {
    aVal = aVal.toLowerCase();
    bVal = bVal.toLowerCase();
  }

  if (aVal < bVal) return dir === 'asc' ? -1 : 1;
  if (aVal > bVal) return dir === 'asc' ? 1 : -1;
  return 0;
}

/** Get color for exit reason — expanded palette */
function getExitReasonColor(reason: string): string {
  const normalized = reason.toUpperCase().replace(/^OPT_/, '');
  if (['ENERGY_WINNER_FADING', 'TRAIL', 'PEAK_TRAIL'].includes(normalized)) return '#00c853';
  if (['RATCHET', 'TP'].includes(normalized)) return '#ffd600';
  if (['ENERGY_DEAD_LOSER', 'ENTRY_DROP', 'STALE'].includes(normalized)) return '#ff9100';
  if (normalized === 'SL') return '#ff1744';
  if (normalized === 'EXPIRY_GUARD') return '#7c4dff';
  if (['UNKNOWN', 'DUPLICATE_UNMATCHED'].includes(normalized)) return '#4b5563';
  return '#9ca3af';
}

function getExitReasonDisplay(reason: string): string {
  return reason.replace(/^OPT_/, '');
}

/** Parse exit reason from trade reason field (fallback for older trades without exit_reason column) */
function parseExitReason(reason?: string | null): string | null {
  if (!reason) return null;
  const upper = reason.toUpperCase().trim();
  // Check from most specific to least (HARD_TP before TP)
  const keywords = ['OPT_MOMENTUM_FADE', 'OPT_DEAD_MOMENTUM', 'OPT_ENERGY_DEAD_LOSER',
    'OPT_ENERGY_WINNER_FADING', 'OPT_HARD_SL', 'OPT_TIMEOUT',
    'OPT_SL', 'OPT_TRAIL', 'OPT_RATCHET', 'OPT_REVERSAL',
    'HARD_TP', 'PROFIT_LOCK', 'DEAD_MOMENTUM', 'MOMENTUM_FADE',
    'DECAY_EMERGENCY', 'MANUAL_CLOSE', 'SPOT_PULLBACK', 'SPOT_DECAY', 'SPOT_BREAKEVEN',
    'TRAIL', 'TP', 'SL', 'FLAT', 'TIMEOUT', 'BREAKEVEN', 'REVERSAL', 'PULLBACK',
    'DECAY', 'SAFETY', 'EXPIRY'];
  for (const kw of keywords) {
    if (upper.includes(kw)) return kw === 'MANUAL_CLOSE' ? 'MANUAL' : kw;
  }
  // Direct matches
  const direct: Record<string, string> = {
    'PHANTOM_CLEARED': 'PHANTOM', 'SL_EXCHANGE': 'SL_EXCHANGE',
    'TP_EXCHANGE': 'TP_EXCHANGE', 'CLOSED_BY_EXCHANGE': 'CLOSED_BY_EXCHANGE',
    'POSITION_GONE': 'POSITION_GONE', 'DUST_UNSELLABLE': 'DUST',
    'ORPHAN_CLOSED': 'ORPHAN', 'ORPHAN_STRATEGY_REMOVED': 'ORPHAN',
    'POSITION_NOT_FOUND_ON_RESTART': 'POSITION_GONE',
  };
  for (const [key, val] of Object.entries(direct)) {
    if (upper.includes(key)) return val;
  }
  if (reason.length <= 10) return reason.toUpperCase();
  return null;
}

/** Get exit reason: prefer exit_reason column, fall back to parsing reason field */
function getExitReason(trade: Trade): string | null {
  if (trade.exit_reason) return trade.exit_reason;
  return parseExitReason(trade.reason);
}

/** Calculate hold time in seconds for a trade */
function calcHoldSeconds(trade: Trade, now: number): number {
  const openedMs = new Date(trade.timestamp).getTime();
  if (trade.status !== 'open' && trade.closed_at) {
    const closedMs = new Date(trade.closed_at).getTime();
    return Math.max(0, (closedMs - openedMs) / 1000);
  }
  // Open trade: use current time
  return Math.max(0, (now - openedMs) / 1000);
}

/** Live hold-time cell for open trades — ticks via shared `now` timestamp */
function HoldTimeCell({ trade, now }: { trade: Trade; now: number }) {
  if (trade.status !== 'open') {
    // Closed trade: static duration
    if (trade.closed_at) {
      return (
        <span className="font-mono text-zinc-400 text-xs">
          {formatDuration(calcHoldSeconds(trade, now))}
        </span>
      );
    }
    return <span className="text-zinc-600">&mdash;</span>;
  }
  // Open trade: live counter
  const seconds = calcHoldSeconds(trade, now);
  return (
    <span className="font-mono text-xs text-zinc-200">
      <span className="text-red-500 mr-1">&#x1F534;</span>
      {formatDuration(seconds)}
    </span>
  );
}

/** Extract base asset from a pair string, e.g. "SOL/USD:USD" → "SOL" */
function extractBaseAsset(pair: string): string {
  if (pair.includes('/')) return pair.split('/')[0];
  return pair.replace(/USD.*$/, '');
}

/** Clean pair name for display: "ETH/USD:USD" → "ETH/USD" */
function displayPair(pair: string): string {
  return pair.replace(/:USD$/, '');
}

/**
 * Calculate unrealized P&L for an open trade using the latest market price.
 * Returns { pnl, pnl_pct } or null if we can't calculate.
 */
function calcUnrealizedPnL(
  trade: Trade,
  currentPrice: number | null,
): { pnl: number; pnl_pct: number } | null {
  if (currentPrice == null || currentPrice <= 0) return null;
  if (trade.status !== 'open') return null;

  const entryPrice = trade.price;
  const contracts = trade.contracts ?? trade.amount;
  if (!entryPrice || !contracts) return null;

  const isOption = isOptionTrade(trade);
  const leverage = trade.leverage > 1 ? trade.leverage : 1;

  if (isOption) {
    // Options: P&L = (current - entry) × contracts × CONTRACT_MULTIPLIER
    const asset = extractBaseAsset(trade.pair);
    const multiplier = OPTION_CONTRACT_MULTIPLIER[asset] ?? 0.01;
    const coinAmount = contracts * multiplier;
    const grossPnl = trade.position_type === 'short'
      ? (entryPrice - currentPrice) * coinAmount
      : (currentPrice - entryPrice) * coinAmount;
    // Return % = premium move (do NOT multiply by leverage)
    const pnlPct = entryPrice > 0 ? ((currentPrice - entryPrice) / entryPrice) * 100 : 0;
    return { pnl: grossPnl, pnl_pct: trade.position_type === 'short' ? -pnlPct : pnlPct };
  }

  // Futures
  let coinAmount = contracts;
  if (trade.exchange === 'delta') {
    const contractSize = DELTA_CONTRACT_SIZE[trade.pair] ?? 1.0;
    coinAmount = contracts * contractSize;
  }

  let grossPnl: number;
  if (trade.position_type === 'short') {
    grossPnl = (entryPrice - currentPrice) * coinAmount;
  } else {
    grossPnl = (currentPrice - entryPrice) * coinAmount;
  }

  const notional = entryPrice * coinAmount;
  const collateral = notional / leverage;
  const pnlPct = collateral > 0 ? (grossPnl / collateral) * 100 : 0;

  return { pnl: grossPnl, pnl_pct: pnlPct };
}

/** Build a PositionDisplay from a Trade + current price (for range bar / state badge) */
function buildPositionDisplay(
  trade: Trade,
  currentPrice: number | null,
  optionsState?: OptionsState[],
): PositionDisplay | null {
  if (trade.status !== 'open') return null;

  const asset = extractBaseAsset(trade.pair);
  const leverage = trade.leverage > 1 ? trade.leverage : 1;
  const entry = trade.price;

  let pricePnlPct: number | null = null;
  let capitalPnlPct: number | null = null;
  let pnlUsd: number | null = null;
  let collateral: number | null = null;

  const isOption = isOptionTrade(trade);

  if (currentPrice != null && entry > 0) {
    if (trade.position_type === 'short') {
      pricePnlPct = ((entry - currentPrice) / entry) * 100;
    } else {
      pricePnlPct = ((currentPrice - entry) / entry) * 100;
    }

    if (isOption) {
      // Options: P&L = (current - entry) × contracts × CONTRACT_MULTIPLIER
      const contracts = trade.contracts ?? trade.amount;
      const multiplier = OPTION_CONTRACT_MULTIPLIER[asset] ?? 0.01;
      const coinAmount = contracts * multiplier;
      if (trade.position_type === 'short') {
        pnlUsd = (entry - currentPrice) * coinAmount;
      } else {
        pnlUsd = (currentPrice - entry) * coinAmount;
      }
      // Return % = premium move (do NOT multiply by leverage)
      capitalPnlPct = pricePnlPct;
      collateral = entry * coinAmount;
    } else {
      // Futures
      let coinAmount = trade.contracts ?? trade.amount;
      if (trade.exchange === 'delta') {
        const contractSize = DELTA_CONTRACT_SIZE[trade.pair] ?? 1.0;
        coinAmount = (trade.contracts ?? trade.amount) * contractSize;
      }
      if (trade.position_type === 'short') {
        pnlUsd = (entry - currentPrice) * coinAmount;
      } else {
        pnlUsd = (currentPrice - entry) * coinAmount;
      }
      const notional = entry * coinAmount;
      capitalPnlPct = pricePnlPct * leverage;
      collateral = leverage > 1 ? notional / leverage : notional;
    }
  }

  const peakPnlPct = trade.peak_pnl ?? (pricePnlPct != null && pricePnlPct > 0 ? pricePnlPct : 0);

  // Options trail activates at 15% premium gain, futures at 0.15% spot
  const trailThreshold = isOption ? OPT_TRAIL_ACTIVATION_PCT : TRAIL_ACTIVATION_PCT;
  const trailActive = (
    trade.position_state === 'trailing'
    && peakPnlPct >= trailThreshold
  );

  let trailStopPrice: number | null = trade.trail_stop_price ?? null;
  if (trailStopPrice == null && trailActive && currentPrice != null && pricePnlPct != null) {
    if (isOption) {
      // Options: trail 5% behind peak premium (matches engine OPT_TRAIL_DISTANCE_PCT)
      const trailDist = OPT_TRAIL_DISTANCE_PCT;
      trailStopPrice = currentPrice * (1 - trailDist / 100);
    } else {
      // Futures: tiered trail distance
      let trailDist = 0.30;
      const tiers: [number, number][] = [[0.50, 0.30], [1.00, 0.50], [2.00, 0.70], [3.00, 1.00]];
      for (const [minProfit, dist] of tiers) {
        if (pricePnlPct >= minProfit) trailDist = dist;
      }
      if (trade.position_type === 'short') {
        trailStopPrice = currentPrice * (1 + trailDist / 100);
      } else {
        trailStopPrice = currentPrice * (1 - trailDist / 100);
      }
    }
  }

  // Extract options strike/expiry from optionsState
  let optionStrike: number | null = null;
  let optionExpiry: string | null = null;
  if (isOption && optionsState) {
    const pairKey = `${asset}/USD:USD`;
    const optState = optionsState.find((s) => s.pair === pairKey);
    optionStrike = optState?.position_strike ?? null;
    optionExpiry = optState?.expiry_label ?? null;
  }

  const openedMs = new Date(trade.timestamp).getTime();
  const mins = Math.floor((Date.now() - openedMs) / 60000);
  const duration = mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h${mins % 60}m`;

  return {
    id: trade.id,
    pair: trade.pair,
    pairShort: asset,
    positionType: trade.position_type as 'long' | 'short',
    entryPrice: entry,
    currentPrice,
    contracts: trade.contracts ?? trade.amount,
    leverage,
    pricePnlPct,
    capitalPnlPct,
    pnlUsd,
    collateral,
    duration,
    trailActive,
    trailStopPrice,
    peakPnlPct,
    slPrice: trade.stop_loss ?? null,
    tpPrice: trade.take_profit ?? null,
    exchange: trade.exchange,
    isOption,
    optionSide: isOption ? getOptionSide(trade.pair) : null,
    optionStrike,
    optionExpiry,
    // Momentum fade / dead momentum timer state
    fadeTimerActive: trade.fade_timer_active ?? false,
    fadeElapsed: trade.fade_elapsed ?? null,
    fadeRequired: trade.fade_required ?? null,
    deadTimerActive: trade.dead_timer_active ?? false,
    deadElapsed: trade.dead_elapsed ?? null,
    deadRequired: trade.dead_required ?? null,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TradeTable({ trades }: TradeTableProps) {
  const { strategyLog, optionsState } = useSupabase();
  const hasOpenTrades = trades.some((t) => t.status === 'open');
  const livePrices = useLivePrices(hasOpenTrades);

  // -- Scroll sync refs for top + bottom scrollbars ------------------------
  const topScrollRef = useRef<HTMLDivElement>(null);
  const tableScrollRef = useRef<HTMLDivElement>(null);

  // -- Dynamic top scrollbar width (matches actual table scroll width) -----
  const [tableScrollWidth, setTableScrollWidth] = useState(2100);
  useEffect(() => {
    const el = tableScrollRef.current;
    if (!el) return;
    const update = () => setTableScrollWidth(el.scrollWidth);
    update(); // initial
    const obs = new ResizeObserver(update);
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // -- Close trade handler ---------------------------------------------------
  const [closingIds, setClosingIds] = useState<Set<string>>(new Set());
  const handleClose = useCallback(async (posId: string, pair: string) => {
    const sb = getSupabase();
    if (!sb) return;
    setClosingIds((prev) => new Set(prev).add(posId));
    try {
      const { error } = await sb.from('bot_commands').insert({
        command: 'close_trade',
        params: { trade_id: Number(posId), pair },
      });
      if (error) {
        console.error('[Alpha] close_trade command failed:', error.message);
        setClosingIds((prev) => { const next = new Set(prev); next.delete(posId); return next; });
      }
    } catch (e) {
      console.error('[Alpha] close_trade insert error:', e);
      setClosingIds((prev) => { const next = new Set(prev); next.delete(posId); return next; });
    }
  }, []);

  // -- Live timer for open trade hold times --------------------------------
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const hasOpen = trades.some((t) => t.status === 'open');
    if (!hasOpen) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [trades]);

  // -- Filter state ---------------------------------------------------------
  const [strategyFilter, setStrategyFilter] = useState<Strategy | 'All'>('All');
  const [exchangeFilterLocal, setExchangeFilterLocal] = useState<Exchange | 'All'>('All');
  const [positionTypeFilter, setPositionTypeFilter] = useState<PositionType | 'All'>('All');
  const [pnlFilter, setPnlFilter] = useState<PnLFilter>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [search, setSearch] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Count active filters for badge
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (strategyFilter !== 'All') count++;
    if (exchangeFilterLocal !== 'All') count++;
    if (positionTypeFilter !== 'All') count++;
    if (pnlFilter !== 'all') count++;
    if (dateFrom) count++;
    if (dateTo) count++;
    if (search.trim()) count++;
    return count;
  }, [strategyFilter, exchangeFilterLocal, positionTypeFilter, pnlFilter, dateFrom, dateTo, search]);

  // -- Sort state -----------------------------------------------------------
  const [sortKey, setSortKey] = useState<string>('timestamp');
  const [sortDir, setSortDir] = useState<SortDirection>('desc');

  // -- Pagination state -----------------------------------------------------
  const [page, setPage] = useState(1);

  // -- Build current price map from strategy_log ----------------------------
  const currentPrices = useMemo(() => {
    const prices = new Map<string, number>();
    for (const log of strategyLog) {
      if (log.current_price && log.pair) {
        const asset = extractBaseAsset(log.pair);
        if (!prices.has(asset)) {
          prices.set(asset, log.current_price);
        }
      }
    }
    return prices;
  }, [strategyLog]);

  // -- Derived: filtered & sorted trades with open/closed separation --------
  const { openTrades, closedTrades, filteredTrades } = useMemo(() => {
    let result = trades;

    // Strategy filter
    if (strategyFilter !== 'All') {
      result = result.filter((t) => t.strategy === strategyFilter);
    }

    // Exchange filter
    if (exchangeFilterLocal !== 'All') {
      result = result.filter((t) => t.exchange === exchangeFilterLocal);
    }

    // Position type filter
    if (positionTypeFilter !== 'All') {
      result = result.filter((t) => t.position_type === positionTypeFilter);
    }

    // P&L filter
    if (pnlFilter === 'profit') {
      result = result.filter((t) => t.pnl > 0);
    } else if (pnlFilter === 'loss') {
      result = result.filter((t) => t.pnl < 0);
    }

    // Date range
    if (dateFrom) {
      const from = new Date(dateFrom).getTime();
      result = result.filter((t) => new Date(t.timestamp).getTime() >= from);
    }
    if (dateTo) {
      const to = new Date(dateTo).getTime() + 86_399_999;
      result = result.filter((t) => new Date(t.timestamp).getTime() <= to);
    }

    // Search by pair name
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter((t) => t.pair.toLowerCase().includes(q));
    }

    // Split into open and closed/cancelled
    const open = result
      .filter((t) => t.status === 'open')
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    const closed = result
      .filter((t) => t.status !== 'open')
      .sort((a, b) => compareTrades(a, b, sortKey, sortDir));

    // Combined: open first, then closed
    const combined = [...open, ...closed];

    return { openTrades: open, closedTrades: closed, filteredTrades: combined };
  }, [trades, strategyFilter, exchangeFilterLocal, positionTypeFilter, pnlFilter, dateFrom, dateTo, search, sortKey, sortDir]);

  // -- Derived: pagination --------------------------------------------------
  const totalPages = Math.max(1, Math.ceil(filteredTrades.length / TRADES_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * TRADES_PER_PAGE;
  const endIdx = Math.min(startIdx + TRADES_PER_PAGE, filteredTrades.length);
  const visibleTrades = filteredTrades.slice(startIdx, endIdx);

  // -- Handlers -------------------------------------------------------------
  const handleSort = useCallback(
    (key: string) => {
      if (key === 'exit_price' || key === 'id' || key === 'hold_time' || key === 'exit_reason' || key === 'fees' || key === 'gross_pnl' || key === 'setup_type' || key === 'sl_price' || key === 'trail_info' || key === 'peak_info') return; // Not sortable
      if (key === sortKey) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortKey(key);
        setSortDir('desc');
      }
      setPage(1);
    },
    [sortKey],
  );

  const handleStrategyFilter = useCallback((value: Strategy | 'All') => {
    setStrategyFilter(value);
    setPage(1);
  }, []);

  const handleExchangeFilter = useCallback((value: Exchange | 'All') => {
    setExchangeFilterLocal(value);
    setPage(1);
  }, []);

  const handlePositionTypeFilter = useCallback((value: PositionType | 'All') => {
    setPositionTypeFilter(value);
    setPage(1);
  }, []);

  const handlePnlFilter = useCallback((value: PnLFilter) => {
    setPnlFilter(value);
    setPage(1);
  }, []);

  const handleDateFrom = useCallback((value: string) => {
    setDateFrom(value);
    setPage(1);
  }, []);

  const handleDateTo = useCallback((value: string) => {
    setDateTo(value);
    setPage(1);
  }, []);

  const handleSearch = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const exportCSV = useCallback(() => {
    const csv = tradesToCSV(filteredTrades as unknown as Array<Record<string, unknown>>);
    if (!csv) return;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `trades_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [filteredTrades]);

  // -- Render helpers -------------------------------------------------------
  const filterBtnBase =
    'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors';
  const filterBtnActive = 'bg-zinc-700 text-white';
  const filterBtnInactive = 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800';

  /** Get P&L display values for a trade (realized or unrealized) */
  function getDisplayPnL(trade: Trade): { pnl: number; pnlPct: number | null; grossPnl: number | null; isUnrealized: boolean } {
    if (trade.status === 'closed') {
      // All closed trades (options AND futures): read P&L from DB directly.
      // The engine writes gross_pnl, pnl (net), and pnl_pct with the correct
      // formula for each instrument type. Do NOT recalculate in the dashboard.
      return {
        pnl: trade.pnl,
        pnlPct: trade.pnl_pct ?? null,
        grossPnl: trade.gross_pnl ?? null,
        isUnrealized: false,
      };
    }

    if (trade.status === 'open') {
      // Options: calculate live P&L from current_premium in options_state
      // Formula: (current_premium - entry_price) × contracts × multiplier
      if (isOptionTrade(trade) && trade.price > 0) {
        const asset = extractBaseAsset(trade.pair);
        const pairKey = `${asset}/USD:USD`;
        const optState = optionsState.find((s) => s.pair === pairKey);
        
        const entryPrice = trade.price;
        const contracts = trade.contracts ?? trade.amount ?? 0;
        const multiplier = OPTION_CONTRACT_MULTIPLIER[asset] ?? 0.01;

        // Priority 1: deterministic per-trade calculation using current premium.
        // This avoids mismatches when options_state.pnl_usd reflects a different
        // contract size or a stale position snapshot.
        const currentPremium = optState?.current_premium ?? null;
        if (currentPremium != null && currentPremium > 0 && contracts > 0) {
          const direction = trade.position_type === 'short' ? -1 : 1;
          const grossPnl = direction * (currentPremium - entryPrice) * contracts * multiplier;
          const pnlPct = entryPrice > 0 ? direction * ((currentPremium - entryPrice) / entryPrice) * 100 : 0;
          return { pnl: grossPnl, pnlPct, grossPnl, isUnrealized: true };
        }

        // Priority 2: Use engine-provided pnl as fallback if premium is unavailable.
        if (optState?.pnl_usd != null) {
          return { pnl: optState.pnl_usd, pnlPct: optState.pnl_pct ?? 0, grossPnl: optState.pnl_usd, isUnrealized: true };
        }

        // Priority 3: Try live prices API as fallback
        const currentPrice = livePrices.prices[trade.pair] ?? trade.current_price ?? null;
        if (currentPrice != null && currentPrice > 0 && contracts > 0) {
          const direction = trade.position_type === 'short' ? -1 : 1;
          const grossPnl = direction * (currentPrice - entryPrice) * contracts * multiplier;
          const pnlPct = entryPrice > 0 ? direction * ((currentPrice - entryPrice) / entryPrice) * 100 : 0;
          return { pnl: grossPnl, pnlPct, grossPnl, isUnrealized: true };
        }

        // Last fallback: show zeros with "live" tag so user knows it's updating
        return { pnl: 0, pnlPct: 0, grossPnl: 0, isUnrealized: true };
      }

      const asset = extractBaseAsset(trade.pair);
      // Priority: live API price (3s) → bot DB price (~10s) → strategy_log price (~5min)
      const currentPrice = livePrices.prices[trade.pair] ?? trade.current_price ?? currentPrices.get(asset) ?? null;
      const unrealized = calcUnrealizedPnL(trade, currentPrice);
      if (unrealized) {
        return {
          pnl: unrealized.pnl,
          pnlPct: unrealized.pnl_pct,
          grossPnl: unrealized.pnl,
          isUnrealized: true,
        };
      }
    }

    return { pnl: trade.pnl, pnlPct: trade.pnl_pct ?? null, grossPnl: trade.gross_pnl ?? null, isUnrealized: false };
  }

  // -------------------------------------------------------------------------
  return (
    <div className="space-y-4">
      {/* ----------------------------------------------------------------- */}
      {/* Filters                                                           */}
      {/* ----------------------------------------------------------------- */}

      {/* Mobile: collapsible filter toggle */}
      <div className="lg:hidden">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFiltersOpen((v) => !v)}
            className="flex h-9 items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
              <path fillRule="evenodd" d="M2.628 1.601C5.028 1.206 7.49 1 10 1s4.973.206 7.372.601a.75.75 0 0 1 .628.74v2.288a2.25 2.25 0 0 1-.659 1.59l-4.682 4.683a2.25 2.25 0 0 0-.659 1.59v3.037c0 .684-.31 1.33-.844 1.757l-1.937 1.55A.75.75 0 0 1 8 18.25v-5.757a2.25 2.25 0 0 0-.659-1.591L2.659 6.22A2.25 2.25 0 0 1 2 4.629V2.34a.75.75 0 0 1 .628-.74Z" clipRule="evenodd" />
            </svg>
            Filters
            {activeFilterCount > 0 && (
              <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-blue-500 px-1 text-[10px] font-bold text-white">
                {activeFilterCount}
              </span>
            )}
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className={cn('h-3 w-3 transition-transform', filtersOpen && 'rotate-180')}>
              <path fillRule="evenodd" d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
            </svg>
          </button>
          <button
            onClick={exportCSV}
            disabled={filteredTrades.length === 0}
            className="flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
              <path d="M2 3.5A1.5 1.5 0 0 1 3.5 2h2.879a1.5 1.5 0 0 1 1.06.44l1.122 1.12A1.5 1.5 0 0 0 9.62 4H12.5A1.5 1.5 0 0 1 14 5.5v1.382a1.5 1.5 0 0 1-.44 1.06l-.293.294a1 1 0 0 0-.293.707V12.5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 12.5v-9Z" />
            </svg>
          </button>
        </div>
        {filtersOpen && (
          <div className="mt-2 space-y-3 rounded-lg border border-zinc-700/50 bg-zinc-800/50 p-3">
            {/* P&L filter */}
            <div className="flex flex-wrap gap-3">
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-zinc-400">P&L</span>
                <div className="flex gap-1">
                  {PNL_OPTIONS.map((opt) => (
                    <button key={opt.value} onClick={() => handlePnlFilter(opt.value)} className={cn(filterBtnBase, pnlFilter === opt.value ? filterBtnActive : filterBtnInactive)}>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            {/* Date range + Search */}
            <div className="flex flex-wrap gap-3">
              <div className="space-y-1.5 flex-1 min-w-[200px]">
                <span className="text-xs font-medium text-zinc-400">Date Range</span>
                <div className="flex items-center gap-2">
                  <input type="date" value={dateFrom} onChange={(e) => handleDateFrom(e.target.value)} className="h-9 flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-2 text-xs text-zinc-200 outline-none focus:border-zinc-500" />
                  <span className="text-zinc-500">&ndash;</span>
                  <input type="date" value={dateTo} onChange={(e) => handleDateTo(e.target.value)} className="h-9 flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-2 text-xs text-zinc-200 outline-none focus:border-zinc-500" />
                </div>
              </div>
              <div className="space-y-1.5 flex-1 min-w-[120px]">
                <span className="text-xs font-medium text-zinc-400">Search</span>
                <input type="text" value={search} onChange={(e) => handleSearch(e.target.value)} placeholder="Search pair..." className="h-9 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-xs text-zinc-200 placeholder-zinc-500 outline-none focus:border-zinc-500" />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Desktop: filters always visible */}
      <div className="hidden lg:flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-zinc-400">P&L</span>
            <div className="flex gap-1">
              {PNL_OPTIONS.map((opt) => (
                <button key={opt.value} onClick={() => handlePnlFilter(opt.value)} className={cn(filterBtnBase, pnlFilter === opt.value ? filterBtnActive : filterBtnInactive)}>
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-zinc-400">Date Range</span>
            <div className="flex items-center gap-2">
              <input type="date" value={dateFrom} onChange={(e) => handleDateFrom(e.target.value)} className="h-8 rounded-lg border border-zinc-700 bg-zinc-800 px-2 text-xs text-zinc-200 outline-none focus:border-zinc-500" />
              <span className="text-zinc-500">&ndash;</span>
              <input type="date" value={dateTo} onChange={(e) => handleDateTo(e.target.value)} className="h-8 rounded-lg border border-zinc-700 bg-zinc-800 px-2 text-xs text-zinc-200 outline-none focus:border-zinc-500" />
            </div>
          </div>
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-zinc-400">Search</span>
            <input type="text" value={search} onChange={(e) => handleSearch(e.target.value)} placeholder="Search pair..." className="h-8 w-40 rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-xs text-zinc-200 placeholder-zinc-500 outline-none focus:border-zinc-500" />
          </div>
        </div>
        <button
          onClick={exportCSV}
          disabled={filteredTrades.length === 0}
          className="flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
            <path d="M2 3.5A1.5 1.5 0 0 1 3.5 2h2.879a1.5 1.5 0 0 1 1.06.44l1.122 1.12A1.5 1.5 0 0 0 9.62 4H12.5A1.5 1.5 0 0 1 14 5.5v1.382a1.5 1.5 0 0 1-.44 1.06l-.293.294a1 1 0 0 0-.293.707V12.5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 12.5v-9Z" />
          </svg>
          Export CSV
        </button>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Summary bar                                                        */}
      {/* ----------------------------------------------------------------- */}
      <div className="flex items-center gap-4 text-xs text-zinc-400">
        <span>{openTrades.length} open</span>
        <span className="text-zinc-700">|</span>
        <span>{closedTrades.length} closed</span>
        <span className="text-zinc-700">|</span>
        <span>{filteredTrades.length} total</span>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Mobile card view                                                   */}
      {/* ----------------------------------------------------------------- */}
      <div className="md:hidden">
        {visibleTrades.length === 0 ? (
          <div className="rounded-xl border border-zinc-800 bg-card px-4 py-16 text-center text-sm text-zinc-500">
            No trades match your filters
          </div>
        ) : (
          <div className="space-y-2">
            {visibleTrades.map((trade, idx) => {
              const display = getDisplayPnL(trade);
              // Show section divider between open and closed
              const prevTrade = idx > 0 ? visibleTrades[idx - 1] : null;
              const showDivider = prevTrade?.status === 'open' && trade.status !== 'open';

              return (
                <div key={trade.id}>
                  {showDivider && (
                    <div className="flex items-center gap-2 py-2">
                      <div className="flex-1 border-t border-zinc-700" />
                      <span className="text-[10px] uppercase tracking-wider text-zinc-500">Closed Trades</span>
                      <div className="flex-1 border-t border-zinc-700" />
                    </div>
                  )}
                  <div className={cn(
                    'border rounded-lg p-3',
                    trade.status === 'open'
                      ? 'bg-zinc-900/60 border-zinc-700'
                      : 'bg-zinc-900/40 border-zinc-800/50',
                  )}>
                    {/* Top row: Pair + Type + P&L */}
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-zinc-500">
                          #{typeof trade.id === 'string' && trade.id.length > 6
                            ? trade.id.slice(-6)
                            : trade.id}
                        </span>
                        <span className="text-sm font-semibold text-white">
                          {isOptionTrade(trade) ? displayOptionPair(trade.pair) : displayPair(trade.pair)}
                        </span>
                        <span className={cn('text-[10px] font-medium', getPositionTypeColor(trade.position_type))}>
                          {isOptionTrade(trade) ? 'OPT' : getPositionTypeLabel(trade.position_type)}
                        </span>
                        <span
                          className="inline-block h-2 w-2 rounded-full"
                          style={{ backgroundColor: getExchangeColor(trade.exchange) }}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="text-right">
                          <span
                            className={cn(
                              'text-sm font-mono font-semibold',
                              getPnLColor(display.pnl),
                            )}
                          >
                            {formatPnL(display.pnl)}
                          </span>
                          {display.isUnrealized && (
                            <span className="text-[9px] text-zinc-500 ml-1">live</span>
                          )}
                          {trade.status === 'closed' && (display.grossPnl != null || trade.gross_pnl != null) && (
                            <div className="text-[10px] text-zinc-500 font-mono">
                              gross {formatPnL(display.grossPnl ?? trade.gross_pnl ?? 0)} · fees -${((trade.entry_fee ?? 0) + (trade.exit_fee ?? 0)).toFixed(4)}
                            </div>
                          )}
                        </div>
                        {trade.status === 'open' && (
                          <button
                            onClick={() => handleClose(String(trade.id), trade.pair)}
                            disabled={closingIds.has(String(trade.id))}
                            className={cn(
                              'px-2 py-1 rounded text-[10px] font-semibold',
                              closingIds.has(String(trade.id))
                                ? 'bg-zinc-700/50 text-zinc-500 cursor-wait'
                                : 'bg-[#ff1744]/10 text-[#ff1744] active:bg-[#ff1744]/20',
                            )}
                          >
                            {closingIds.has(String(trade.id)) ? 'Closing...' : 'Close'}
                          </button>
                        )}
                      </div>
                    </div>
                    {/* Prices row */}
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs mb-1">
                      <span className="text-zinc-400">
                        Entry: <span className="font-mono text-zinc-300">
                          {isOptionTrade(trade) ? formatPrice(trade.price) : formatPrice(trade.price)}
                        </span>
                      </span>
                      {trade.exit_price != null && (
                        <span className="text-zinc-400">
                          Exit: <span className="font-mono text-zinc-300">
                            {isOptionTrade(trade) ? formatPrice(trade.exit_price) : formatPrice(trade.exit_price)}
                          </span>
                        </span>
                      )}
                      {trade.exchange === 'delta' && (
                        <span className="text-zinc-500 font-mono">
                          {trade.contracts ?? trade.amount} {isOptionTrade(trade) ? 'opt' : 'contracts'}
                        </span>
                      )}
                    </div>
                    {/* Details row */}
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-400">
                      <span>{formatDate(trade.timestamp)}</span>
                      <Badge variant={getStrategyBadgeVariant(trade.strategy)}>
                        {getStrategyLabel(trade.strategy)}
                      </Badge>
                      {inferSetupType(trade) && (
                        <SetupChip setup={inferSetupType(trade)} />
                      )}
                      {trade.leverage > 1 && (
                        <span className="text-amber-400 font-mono">{formatLeverage(trade.leverage)}</span>
                      )}
                      {display.pnlPct != null && (
                        <span className={cn('font-mono', getPnLColor(display.pnlPct))}>
                          {isOptionTrade(trade) && display.pnlPct < -100
                            ? '-100% (liq)'
                            : formatPercentage(display.pnlPct)}
                          {display.isUnrealized ? ' (unr)' : ''}
                        </span>
                      )}
                      {trade.peak_pnl != null && trade.status === 'closed' && (() => {
                        const taken = display.pnlPct ?? 0;
                        const peak = trade.peak_pnl;
                        const capture = peak > 0 ? Math.round((taken / peak) * 100) : null;
                        return (
                          <span className="font-mono text-zinc-400">
                            <span className={cn(
                              peak >= 0.3 ? 'text-emerald-400' :
                              peak >= 0.1 ? 'text-yellow-400' :
                              peak >= 0 ? 'text-zinc-400' : 'text-red-400'
                            )}>
                              pk {peak >= 0 ? '+' : ''}{peak.toFixed(2)}%
                            </span>
                            {capture != null && (
                              <span className={cn(
                                'ml-1',
                                capture >= 80 ? 'text-emerald-400' :
                                capture >= 50 ? 'text-yellow-400' :
                                capture >= 0 ? 'text-orange-400' : 'text-red-400'
                              )}>
                                ({capture}%)
                              </span>
                            )}
                          </span>
                        );
                      })()}
                      <HoldTimeCell trade={trade} now={now} />
                      {trade.status === 'open' && (() => {
                        const asset = extractBaseAsset(trade.pair);
                        // Priority: live API (3s) → bot DB price (~10s) → strategy_log (~5min)
                        let cp: number | null = livePrices.prices[trade.pair] ?? trade.current_price ?? currentPrices.get(asset) ?? null;
                        // Options: use current_premium from options_state, NOT spot price
                        if (isOptionTrade(trade)) {
                          const optState = optionsState.find((s) => s.pair === `${asset}/USD:USD`);
                          cp = optState?.current_premium ?? null;
                        }
                        const posDisplay = buildPositionDisplay(trade, cp, optionsState);
                        if (!posDisplay) return null;
                        const posState = getPositionState(posDisplay);
                        return (
                          <>
                            <StateBadge
                              state={posState}
                              trailStopPrice={posDisplay.trailStopPrice}
                              entryPrice={posDisplay.entryPrice}
                              pos={posDisplay}
                            />
                            <div className="w-full mt-1">
                              <div className="max-w-[240px]">
                                <PositionRangeBar pos={posDisplay} />
                              </div>
                            </div>
                          </>
                        );
                      })()}
                      {trade.status !== 'open' && (() => {
                        const reason = getExitReason(trade);
                        return reason ? <ExitChip exit={reason} /> : null;
                      })()}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Mobile pagination */}
        {filteredTrades.length > 0 && (
          <div className="flex items-center justify-between mt-3">
            <span className="text-xs text-zinc-400">
              {startIdx + 1}&ndash;{endIdx} of {filteredTrades.length}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
                className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-xs font-medium text-zinc-300 disabled:opacity-40"
              >
                Prev
              </button>
              <span className="text-xs text-zinc-400">
                {safePage}/{totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
                className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-xs font-medium text-zinc-300 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Desktop table                                                      */}
      {/* ----------------------------------------------------------------- */}
      <div className="hidden md:block bg-card overflow-hidden rounded-xl border border-zinc-800">
        {/* Top scrollbar — mirrors the table scroll */}
        <div
          ref={topScrollRef}
          className="overflow-x-auto scrollbar-visible"
          onScroll={() => {
            if (tableScrollRef.current && topScrollRef.current) {
              tableScrollRef.current.scrollLeft = topScrollRef.current.scrollLeft;
            }
          }}
        >
          <div style={{ width: `${tableScrollWidth}px`, height: '1px' }} />
        </div>
        <div
          ref={tableScrollRef}
          className="overflow-auto max-h-[78vh] scrollbar-visible"
          onScroll={() => {
            if (topScrollRef.current && tableScrollRef.current) {
              topScrollRef.current.scrollLeft = tableScrollRef.current.scrollLeft;
            }
          }}
        >
          <table className="w-full min-w-[2100px] text-sm">
            {/* Header — sticky top so it stays visible on vertical scroll */}
            <thead className="sticky top-0 z-30">
              <tr className="bg-zinc-900">
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    className={cn(
                      'cursor-pointer select-none whitespace-nowrap px-4 py-3 text-xs font-medium uppercase tracking-wider text-zinc-400 transition-colors hover:text-zinc-200 bg-zinc-900',
                      col.align === 'right' ? 'text-right' : 'text-left',
                      STICKY_COLS[col.key] && `sticky ${STICKY_COLS[col.key]} z-40 bg-zinc-900`,
                      col.key === LAST_STICKY_COL && 'border-r border-zinc-700',
                    )}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {sortKey === col.key && (
                        <span className="text-zinc-300">
                          {sortDir === 'asc' ? '\u25B2' : '\u25BC'}
                        </span>
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>

            {/* Body */}
            <tbody>
              {visibleTrades.length === 0 ? (
                <tr>
                  <td
                    colSpan={COLUMNS.length}
                    className="px-4 py-16 text-center text-sm text-zinc-500"
                  >
                    No trades match your filters
                  </td>
                </tr>
              ) : (
                visibleTrades.map((trade, idx) => {
                  const display = getDisplayPnL(trade);
                  const prevTrade = idx > 0 ? visibleTrades[idx - 1] : null;
                  const showDivider = prevTrade?.status === 'open' && trade.status !== 'open';

                  return (
                    <>
                      {showDivider && (
                        <tr key={`divider-${trade.id}`}>
                          <td colSpan={COLUMNS.length} className="px-4 py-2 bg-zinc-900/80">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 border-t border-zinc-700" />
                              <span className="text-[10px] uppercase tracking-wider text-zinc-500">Closed Trades</span>
                              <div className="flex-1 border-t border-zinc-700" />
                            </div>
                          </td>
                        </tr>
                      )}
                      <tr
                        key={trade.id}
                        className={cn(
                          'border-b border-zinc-800/50 transition-colors hover:bg-zinc-800/30',
                          trade.status === 'open' && 'bg-zinc-900/30',
                        )}
                      >
                        {/* ── Frozen sticky columns ── */}

                        {/* # (Trade Number) — STICKY */}
                        <td className={cn(
                          'sticky left-0 z-10 whitespace-nowrap px-2 py-3 text-xs font-mono text-zinc-500',
                          trade.status === 'open' ? 'bg-zinc-900' : 'bg-[#0d1117]',
                        )}>
                          #{typeof trade.id === 'string' && trade.id.length > 6
                            ? trade.id.slice(-6)
                            : trade.id}
                        </td>

                        {/* Pair — STICKY */}
                        <td className={cn(
                          'sticky left-[52px] z-10 whitespace-nowrap px-4 py-3 font-medium text-zinc-100',
                          trade.status === 'open' ? 'bg-zinc-900' : 'bg-[#0d1117]',
                        )}>
                          {isOptionTrade(trade) ? (
                            <span title={trade.pair}>
                              {displayOptionPair(trade.pair)}
                              <span className="ml-1 text-[9px] text-pink-400/70 font-mono">OPT</span>
                            </span>
                          ) : displayPair(trade.pair)}
                        </td>

                        {/* Type — STICKY */}
                        <td className={cn(
                          'sticky left-[152px] z-10 whitespace-nowrap px-4 py-3',
                          trade.status === 'open' ? 'bg-zinc-900' : 'bg-[#0d1117]',
                        )}>
                          {isOptionTrade(trade) ? (
                            <span className={cn('text-xs font-medium', trade.pair.endsWith('-C') ? 'text-emerald-400' : 'text-red-400')}>
                              {trade.pair.endsWith('-C') ? 'CALL' : 'PUT'}
                            </span>
                          ) : (
                            <span className={cn('text-xs font-medium', getPositionTypeColor(trade.position_type))}>
                              {getPositionTypeLabel(trade.position_type)}
                            </span>
                          )}
                        </td>

                        {/* Leverage — STICKY */}
                        <td className={cn(
                          'sticky left-[232px] z-10 whitespace-nowrap px-4 py-3 text-right',
                          trade.status === 'open' ? 'bg-zinc-900' : 'bg-[#0d1117]',
                        )}>
                          {isOptionTrade(trade) ? (
                            <span className="text-xs font-medium text-pink-400" title="Options trade — max loss = premium paid">
                              {formatLeverage(trade.leverage)}
                              <span className="text-[8px] text-pink-400/60 ml-0.5">OPT</span>
                            </span>
                          ) : trade.leverage > 1 ? (
                            <span className="text-xs font-medium text-amber-400">
                              {formatLeverage(trade.leverage)}
                            </span>
                          ) : (
                            <span className="text-xs text-zinc-500">&mdash;</span>
                          )}
                        </td>

                        {/* Entry Price — STICKY + right border */}
                        <td className={cn(
                          'sticky left-[292px] z-10 border-r border-zinc-700 whitespace-nowrap px-4 py-3 text-right font-mono text-zinc-300',
                          trade.status === 'open' ? 'bg-zinc-900' : 'bg-[#0d1117]',
                        )}>
                          {formatPrice(trade.price)}
                        </td>

                        {/* ── Scrollable columns ── */}

                        {/* Date */}
                        <td className="whitespace-nowrap px-4 py-3 text-zinc-300">
                          {formatDate(trade.timestamp)}
                        </td>

                        {/* Exchange */}
                        <td className="whitespace-nowrap px-4 py-3">
                          <span className="inline-flex items-center gap-1.5">
                            <span
                              className="inline-block h-2 w-2 rounded-full"
                              style={{ backgroundColor: getExchangeColor(trade.exchange) }}
                            />
                            <span className="text-zinc-300 text-xs">
                              {getExchangeLabel(trade.exchange)}
                            </span>
                          </span>
                        </td>

                        {/* Exit Price */}
                        <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-zinc-300">
                          {trade.exit_price != null ? (
                            formatPrice(trade.exit_price)
                          ) : trade.status === 'open' ? (
                            <span className="text-zinc-500 text-xs italic">open</span>
                          ) : (
                            <span className="text-zinc-600">&mdash;</span>
                          )}
                        </td>

                        {/* Contracts / Amount */}
                        <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-zinc-300">
                          {trade.exchange === 'delta' ? (
                            <span title={isOptionTrade(trade) ? `${trade.contracts ?? trade.amount} option contract(s)` : `${trade.contracts ?? trade.amount} contracts`}>
                              {(trade.contracts ?? trade.amount).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                              <span className="text-zinc-500 text-[10px] ml-0.5">{isOptionTrade(trade) ? 'opt' : 'ct'}</span>
                            </span>
                          ) : (
                            (trade.contracts ?? trade.amount).toLocaleString('en-US', {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 6,
                            })
                          )}
                        </td>

                        {/* Strategy */}
                        <td className="whitespace-nowrap px-4 py-3">
                          <Badge variant={getStrategyBadgeVariant(trade.strategy)}>
                            {getStrategyLabel(trade.strategy)}
                          </Badge>
                        </td>

                        {/* Setup Type */}
                        <td className="whitespace-nowrap px-4 py-3">
                          <SetupChip setup={inferSetupType(trade)} />
                        </td>

                        {/* Gross P&L */}
                        <td
                          className={cn(
                            'whitespace-nowrap px-4 py-3 text-right font-mono text-xs',
                            trade.status === 'open'
                              ? getPnLColor(display.pnl)
                              : getPnLColor(display.grossPnl ?? trade.gross_pnl ?? display.pnl),
                          )}
                        >
                          {trade.status === 'open' ? (
                            <>
                              {formatPnL(display.pnl)}
                              {display.isUnrealized && (
                                <span className="text-[9px] text-zinc-500 ml-0.5 font-normal">live</span>
                              )}
                            </>
                          ) : display.grossPnl != null ? (
                            formatPnL(display.grossPnl)
                          ) : trade.gross_pnl != null ? (
                            formatPnL(trade.gross_pnl)
                          ) : (
                            <span className="text-zinc-600">&mdash;</span>
                          )}
                        </td>

                        {/* Fees (entry + exit) */}
                        <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-xs text-zinc-500">
                          {trade.status === 'closed' && (trade.entry_fee != null || trade.exit_fee != null) ? (
                            <span title={`Entry: $${(trade.entry_fee ?? 0).toFixed(4)} + Exit: $${(trade.exit_fee ?? 0).toFixed(4)}`}>
                              -${((trade.entry_fee ?? 0) + (trade.exit_fee ?? 0)).toFixed(4)}
                            </span>
                          ) : (
                            <span className="text-zinc-600">&mdash;</span>
                          )}
                        </td>

                        {/* Net P&L */}
                        <td
                          className={cn(
                            'whitespace-nowrap px-4 py-3 text-right font-mono font-medium',
                            getPnLColor(display.pnl),
                          )}
                        >
                          {formatPnL(display.pnl)}
                          {display.isUnrealized && (
                            <span className="text-[9px] text-zinc-500 ml-0.5 font-normal">live</span>
                          )}
                          {isOptionTrade(trade) && trade.status === 'closed' && (
                            <div className="text-[9px] text-zinc-500 font-normal mt-0.5"
                                 title={`Collateral: $${(trade.collateral ?? ((trade.price * ((trade.contracts ?? trade.amount) || 1)) / Math.max(trade.leverage, 1))).toFixed(4)} (${trade.leverage}x)`}>
                              risk: ${(trade.collateral ?? ((trade.price * ((trade.contracts ?? trade.amount) || 1)) / Math.max(trade.leverage, 1))).toFixed(4)}
                            </div>
                          )}
                        </td>

                        {/* P&L % (return on collateral) */}
                        <td
                          className={cn(
                            'whitespace-nowrap px-4 py-3 text-right font-mono text-xs',
                            getPnLColor(display.pnlPct ?? 0),
                          )}
                        >
                          {display.pnlPct != null
                            ? (
                              <>
                                {isOptionTrade(trade) && display.pnlPct < -100
                                  ? <span title={`Actual: ${formatPercentage(display.pnlPct)}`}>-100.00% <span className="text-[9px] text-red-500">(liq)</span></span>
                                  : formatPercentage(display.pnlPct)}
                                {display.isUnrealized && (
                                  <span className="text-[9px] text-zinc-500 ml-0.5">unr</span>
                                )}
                                {trade.exit_price != null && trade.status === 'closed' && (() => {
                                  const isShort = trade.position_type === 'short';
                                  const raw = isShort
                                    ? (trade.price - trade.exit_price) / trade.price * 100
                                    : (trade.exit_price - trade.price) / trade.price * 100;
                                  return (
                                    <div className={cn(
                                      'text-[9px] mt-0.5',
                                      raw >= 0 ? 'text-zinc-500' : 'text-red-400/70'
                                    )}>
                                      {raw >= 0 ? '+' : ''}{raw.toFixed(2)}%
                                    </div>
                                  );
                                })()}
                              </>
                            )
                            : trade.status === 'closed' ? '+0.00%' : '—'}
                        </td>

                        {/* Hold Time */}
                        <td className="whitespace-nowrap px-4 py-3 text-right">
                          <HoldTimeCell trade={trade} now={now} />
                        </td>

                        {/* SL Price — GPFC #56: only meaningful for live positions */}
                        <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-xs">
                          {trade.status === 'open' && trade.stop_loss != null ? (
                            <span className="text-red-400">
                              {formatPrice(trade.stop_loss)}
                            </span>
                          ) : (
                            <span />
                          )}
                        </td>

                        {/* Trail Info — Range bar for open, exit label for closed */}
                        <td className="px-4 py-3 text-xs">
                          {trade.status === 'open' ? (() => {
                            const asset = extractBaseAsset(trade.pair);
                            // Priority: live API (3s) → bot DB price (~10s) → strategy_log (~5min)
                            let cp: number | null = livePrices.prices[trade.pair] ?? trade.current_price ?? currentPrices.get(asset) ?? null;
                            if (isOptionTrade(trade)) {
                              const optState = optionsState.find((s) => s.pair === `${asset}/USD:USD`);
                              cp = optState?.current_premium ?? null;
                            }
                            const posDisplay = buildPositionDisplay(trade, cp, optionsState);
                            if (posDisplay) {
                              const posState = getPositionState(posDisplay);
                              return (
                                <div className="min-w-[140px] space-y-1">
                                  <StateBadge
                                    state={posState}
                                    trailStopPrice={posDisplay.trailStopPrice}
                                    entryPrice={posDisplay.entryPrice}
                                    pos={posDisplay}
                                  />
                                  <div className="w-[140px]">
                                    <PositionRangeBar pos={posDisplay} compact />
                                  </div>
                                </div>
                              );
                            }
                            return <span className="text-zinc-600">&mdash;</span>;
                          })() : (
                            // GPFC #56: closed trades — Trail column hidden;
                            // exit info is the dedicated Exit chip.
                            <span />
                          )}
                        </td>

                        {/* Peak P&L */}
                        <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-xs">
                          {trade.peak_pnl != null ? (
                            <span className={cn(
                              trade.peak_pnl >= 0.3 ? 'text-emerald-400' :
                              trade.peak_pnl >= 0.1 ? 'text-yellow-400' :
                              trade.peak_pnl >= 0 ? 'text-zinc-400' : 'text-red-400'
                            )}>
                              {trade.peak_pnl >= 0 ? '+' : ''}{trade.peak_pnl.toFixed(2)}%
                            </span>
                          ) : (
                            <span className="text-zinc-600">&mdash;</span>
                          )}
                        </td>

                        {/* Exit Reason */}
                        <td className="whitespace-nowrap px-4 py-3">
                          {trade.status === 'open' ? (
                            <span className="text-xs font-semibold text-emerald-400">
                              {(trade.position_state || 'LIVE').toUpperCase()}
                            </span>
                          ) : (
                            <ExitChip exit={getExitReason(trade)} />
                          )}
                        </td>

                        {/* Status */}
                        <td className="whitespace-nowrap px-4 py-3">
                          <Badge variant={getStatusBadgeVariant(trade.status)}>
                            {trade.status.charAt(0).toUpperCase() + trade.status.slice(1)}
                          </Badge>
                        </td>
                      </tr>
                    </>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {filteredTrades.length > 0 && (
          <div className="flex items-center justify-between border-t border-zinc-800 px-4 py-3">
            <span className="text-xs text-zinc-400">
              Showing {startIdx + 1}&ndash;{endIdx} of {filteredTrades.length} trades
            </span>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
                className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>

              <span className="min-w-[4rem] text-center text-xs text-zinc-400">
                Page {safePage} of {totalPages}
              </span>

              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
                className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
