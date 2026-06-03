// GPFC #79.2: parse engine exit_reason values into a primary action + phase letter.
// DB stays snake_case (stop_phase_a, trail_phase_c, breakeven, dead, pre_expiry,
// expired_itm, expired_otm). UI renders two pills for phased exits, one pill for
// single-shot exits.
//
// Historical rows may still use old uppercase reasons (TRAIL, PEAK, STOP, DEAD,
// BREAKEVEN, GONE, EXPIRY, etc.) — these flow through unchanged as single pills.

export type ParsedExitReason = {
  primary: string;
  phase: string | null;
  rawKey: string;
};

const SINGLE_PILL_MAP: Record<string, string> = {
  breakeven: "BREAKEVEN",
  dead: "DEAD",
  profit_harvest: "PROFIT",
  pre_expiry: "PRE-EXPIRY",
  peak: "PEAK",
  expired_itm: "EXPIRED ITM",
  expired_otm: "EXPIRED OTM",
  expired_worthless: "EXPIRED OTM",
  ticker_dropout: "TICKER DROPOUT",
  reconcile_gone: "RECONCILE GONE",
};

export function parseExitReason(
  raw: string | null | undefined,
): ParsedExitReason {
  if (!raw) return { primary: "—", phase: null, rawKey: "" };

  const lower = raw.trim().toLowerCase();
  const phased = lower.match(/^(stop|trail)_phase_([a-e])$/);

  if (phased) {
    return {
      primary: phased[1].toUpperCase(),
      phase: phased[2].toUpperCase(),
      rawKey: lower,
    };
  }

  const single = SINGLE_PILL_MAP[lower];
  return {
    primary: single ?? raw.trim().toUpperCase().replace(/_/g, " "),
    phase: null,
    rawKey: lower,
  };
}

/** Tailwind-friendly color keyword for the primary pill. */
export function exitReasonColor(primary: string): string {
  switch (primary) {
    case "STOP":
      return "red";
    case "TRAIL":
      return "green";
    case "BREAKEVEN":
      return "gray";
    case "DEAD":
      return "darkred";
    case "PRE-EXPIRY":
      return "yellow";
    case "PEAK":
    case "PROFIT":
      return "green";
    case "EXPIRED ITM":
      return "green";
    case "EXPIRED OTM":
      return "red";
    case "TICKER DROPOUT":
      return "gray";
    case "RECONCILE GONE":
      return "gray";
    default:
      return "gray";
  }
}
