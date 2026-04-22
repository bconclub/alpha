/**
 * Centralized P&L math. Single source of truth for every widget that
 * shows "Today / 24H / 7D / 14D / 30D / All-time" aggregates.
 *
 * Rules (must match Supabase views in `supabase/schema.sql`):
 *   • Only rows with status === 'closed' count. Open / cancelled are ignored.
 *   • Net P&L  = sum(t.pnl)                      (pnl column is already net of fees)
 *   • Gross    = sum(t.gross_pnl ?? pnl + fees)
 *   • Fees     = sum(t.entry_fee + t.exit_fee)
 *   • Wins     = count where t.pnl > 0 (strict; 0 is neither win nor loss)
 *   • Losses   = count where t.pnl < 0
 *   • WinRate  = wins / (wins+losses) * 100   (excludes flats so a 0-pnl
 *                reconcile-adoption doesn't silently deflate the rate)
 *
 * The shared helpers below take a pre-filtered array of trades (so the
 * caller controls the time window) and return the canonical stats object.
 */

export interface PnLStats {
  total: number;       // closed trades in window
  wins: number;
  losses: number;
  flats: number;       // pnl === 0 (rare; reconciled w/ no price move)
  winRate: number;     // 0-100, excludes flats from denominator
  grossPnl: number;
  fees: number;
  pnl: number;         // net P&L (after fees)
  totalLoss: number;   // sum of negative pnls only (drawdown today)
  bestTrade: number;
  worstTrade: number;
}

export interface MinimalTrade {
  status: string;
  pnl?: number | null;
  gross_pnl?: number | null;
  entry_fee?: number | null;
  exit_fee?: number | null;
}

export function emptyPnLStats(): PnLStats {
  return {
    total: 0, wins: 0, losses: 0, flats: 0, winRate: 0,
    grossPnl: 0, fees: 0, pnl: 0, totalLoss: 0,
    bestTrade: 0, worstTrade: 0,
  };
}

/**
 * Compute canonical P&L stats from a list of trades. Only rows where
 * status === 'closed' are counted — the caller is responsible for any
 * time-window / exchange / strategy filtering before calling this.
 */
export function computePnLStats(trades: readonly MinimalTrade[]): PnLStats {
  const out = emptyPnLStats();
  let best = Number.NEGATIVE_INFINITY;
  let worst = Number.POSITIVE_INFINITY;

  for (const t of trades) {
    if (t.status !== 'closed') continue;
    const pnl = t.pnl ?? 0;
    const fees = (t.entry_fee ?? 0) + (t.exit_fee ?? 0);
    const gross = t.gross_pnl != null ? t.gross_pnl : pnl + fees;

    out.total += 1;
    out.pnl += pnl;
    out.fees += fees;
    out.grossPnl += gross;

    if (pnl > 0) out.wins += 1;
    else if (pnl < 0) { out.losses += 1; out.totalLoss += pnl; }
    else out.flats += 1;

    if (pnl > best) best = pnl;
    if (pnl < worst) worst = pnl;
  }

  const decisive = out.wins + out.losses;
  out.winRate = decisive > 0 ? (out.wins / decisive) * 100 : 0;
  out.bestTrade = best === Number.NEGATIVE_INFINITY ? 0 : best;
  out.worstTrade = worst === Number.POSITIVE_INFINITY ? 0 : worst;
  return out;
}

/**
 * UTC ms corresponding to today's 00:00 in IST (UTC+5:30).
 */
export function istTodayStartMs(nowMs: number = Date.now()): number {
  const istOffsetMs = 5.5 * 60 * 60 * 1000;
  const istNow = new Date(nowMs + istOffsetMs);
  const todayIST = istNow.toISOString().slice(0, 10);
  return new Date(todayIST + 'T00:00:00+05:30').getTime();
}

/**
 * ISO-string version of the IST midnight cutoff — for direct Supabase
 * gte('opened_at', ...) queries.
 */
export function istTodayStartISO(nowMs: number = Date.now()): string {
  const istOffsetMs = 5.5 * 60 * 60 * 1000;
  const istNow = new Date(nowMs + istOffsetMs);
  const todayIST = istNow.toISOString().slice(0, 10);
  return new Date(todayIST + 'T00:00:00+05:30').toISOString();
}

/**
 * Filter helper for "trades opened today in IST". Assumes trade has a
 * `timestamp` field (normalizeTrade maps it to opened_at).
 */
export function isOpenedTodayIST(
  trade: { timestamp?: string | null },
  nowMs: number = Date.now(),
): boolean {
  if (!trade.timestamp) return false;
  const cutoff = istTodayStartMs(nowMs);
  return new Date(trade.timestamp).getTime() >= cutoff;
}
