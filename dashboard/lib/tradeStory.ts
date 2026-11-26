// Plain-English account of a closed trade: what the bot did, what price did,
// and why it got out. Exit keys mirror the engine's exit_reason values
// (engine/alpha/live_trader.py) plus the legacy uppercase reasons.

import { parseExitReason } from '@/lib/exitReason';

export interface TradeStoryInput {
  position_type?: string;
  price: number;
  exit_price?: number | null;
  pnl: number;
  pnl_pct?: number | null;
  peak_pnl?: number | null;
  isOption?: boolean;
}

export interface TradeStory {
  /** "Went up 1.2%" style: what price did between entry and exit. */
  move: string | null;
  /** True when price moved the way the trade needed. */
  moveHelped: boolean | null;
  /** Why the trade closed. */
  why: string;
  /** Set when the trade was meaningfully in profit and gave it back. */
  regret: string | null;
}

const WHY: Record<string, string> = {
  hard_stop: 'It hit the stop-loss and the bot got out.',
  loss_cap: 'Loss reached the safety cap, so the bot cut it before it got worse.',
  trail_stop: 'Price pulled back from its best point and the trailing stop closed it.',
  breakeven_stop: 'Price came back to the entry, so the bot got out flat.',
  profit_take: 'Hit the profit target, so the bot banked it.',
  profit_harvest: 'Hit the profit target, so the bot banked it.',
  time_stop: 'It never got moving, so the bot closed it early.',
  stagnant_exit: 'Price sat still for too long, so the bot closed it.',
  no_traction: 'It never moved in our favour, so the bot closed it.',
  max_hold: 'Held for the maximum time allowed, then closed.',
  closed_manually: 'You closed this one by hand.',
  closed_externally: 'Closed outside the bot, on the exchange.',
  closed_by_legacy_sl: 'Closed by an old stop order left on the exchange.',
  orphan_close_legacy: 'Left over from an old strategy, closed during cleanup.',
  engine_restart: 'Closed when the bot restarted.',
  liquidated: 'The exchange liquidated the position.',
  breakeven: 'Price came back to the entry, so the bot got out flat.',
  dead: 'Momentum died, so the bot closed it.',
  peak: 'Closed near its best point.',
  pre_expiry: 'Closed before the option expired.',
  expired_itm: 'The option expired in the money.',
  expired_otm: 'The option expired worthless.',
  expired_worthless: 'The option expired worthless.',
  reconcile_gone: 'Position was no longer on the exchange, so the record was closed.',
  ticker_dropout: 'Price feed dropped, so the bot closed it.',
};

const LEGACY: Record<string, string> = {
  SL: WHY.hard_stop,
  STOP: WHY.hard_stop,
  TRAIL: WHY.trail_stop,
  TP: WHY.profit_take,
  MANUAL: WHY.closed_manually,
  TIMEOUT: WHY.max_hold,
  BREAKEVEN: WHY.breakeven_stop,
  FLAT: WHY.stagnant_exit,
};

function whyFor(exit: string | null, pnl: number): string {
  if (!exit) return pnl >= 0 ? 'Closed in profit.' : 'Closed at a loss.';
  const parsed = parseExitReason(exit);
  if (WHY[parsed.rawKey]) return WHY[parsed.rawKey];
  if (parsed.phase) {
    return parsed.primary === 'TRAIL' ? WHY.trail_stop : WHY.hard_stop;
  }
  const legacy = LEGACY[exit.trim().toUpperCase().replace(/^OPT_/, '')];
  if (legacy) return legacy;
  return `Closed: ${parsed.primary.toLowerCase()}.`;
}

export function tradeStory(t: TradeStoryInput, exit: string | null): TradeStory {
  const short = t.position_type === 'short';
  let move: string | null = null;
  let moveHelped: boolean | null = null;

  if (t.exit_price != null && t.price > 0) {
    const pct = ((t.exit_price - t.price) / t.price) * 100;
    const abs = Math.abs(pct);
    if (abs < 0.005) {
      move = 'Price barely moved';
    } else {
      move = `Price ${pct > 0 ? 'rose' : 'fell'} ${abs.toFixed(abs < 1 ? 2 : 1)}%`;
      moveHelped = t.isOption ? pct > 0 : short ? pct < 0 : pct > 0;
    }
  }

  const peak = t.peak_pnl ?? null;
  const regret =
    peak != null && peak >= 5 && t.pnl < 0
      ? `Was up ${peak.toFixed(1)}% at its best, then reversed.`
      : null;

  return { move, moveHelped, why: whyFor(exit, t.pnl), regret };
}
