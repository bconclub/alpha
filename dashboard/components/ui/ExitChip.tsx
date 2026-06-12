// GPFC #79.2: two-pill exit display for phased exits (STOP/TRAIL + A-E),
// single pill for non-phased exits (BREAKEVEN, DEAD, PRE-EXPIRY, PEAK,
// EXPIRED ITM/OTM, …). Historical rows with legacy uppercase reasons
// (GONE, EXPIRY, ORPHAN, …) fall through to the single-pill path with
// their existing styling.

import { parseExitReason, exitReasonColor } from "@/lib/exitReason";

// Tailwind classes per color-keyword from exitReasonColor().
const COLOR_STYLES: Record<
  string,
  { bg: string; text: string; ring: string }
> = {
  red:      { bg: "bg-red-500/20",     text: "text-red-400",     ring: "ring-red-500/40" },
  darkred:  { bg: "bg-rose-500/20",    text: "text-rose-300",    ring: "ring-rose-500/40" },
  green:    { bg: "bg-emerald-500/15", text: "text-emerald-400", ring: "ring-emerald-500/30" },
  yellow:   { bg: "bg-amber-500/15",   text: "text-amber-400",   ring: "ring-amber-500/30" },
  violet:   { bg: "bg-violet-500/15",  text: "text-violet-300",  ring: "ring-violet-500/30" },
  gray:     { bg: "bg-zinc-500/15",    text: "text-zinc-400",    ring: "ring-zinc-500/30" },
};

// Legacy uppercase exit_reasons from pre-GPFC-#79 trades. Mapped to a color
// keyword so the same color pipeline applies. Anything not in here AND not
// in exitReasonColor() falls back to gray.
const LEGACY_COLOR: Record<string, string> = {
  TRAIL:     "green",
  PEAK:      "green",
  RATCHET:   "green",
  TP:        "green",
  BLEED:     "yellow",
  STOP:      "red",
  STALLED:   "yellow",
  DEAD:      "darkred",
  REVERSE:   "red",
  TIMEOUT:   "gray",
  EXPIRY:    "yellow",
  GONE:      "gray",
  ORPHAN:    "gray",
  DUPLICATE: "gray",
  MANUAL:    "gray",
  BREAKEVEN: "gray",
};

const FALLBACK = COLOR_STYLES.gray;

function styleFor(primary: string): { bg: string; text: string; ring: string } {
  // Prefer the new color-keyword mapping; fall back to legacy uppercase map.
  const colorKey = exitReasonColor(primary);
  if (colorKey !== "gray") return COLOR_STYLES[colorKey] ?? FALLBACK;
  const legacy = LEGACY_COLOR[primary];
  if (legacy) return COLOR_STYLES[legacy] ?? FALLBACK;
  return FALLBACK;
}

export function ExitChip({ exit }: { exit: string | null | undefined }) {
  if (!exit) return <span className="text-zinc-600">—</span>;

  const { primary, phase } = parseExitReason(exit);
  const style = styleFor(primary);

  return (
    <div className="inline-flex items-center gap-1.5">
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ring-1 ring-inset ${style.bg} ${style.text} ${style.ring}`}
      >
        {primary}
      </span>
      {phase && (
        <span
          className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-mono font-semibold ring-1 ring-inset bg-transparent text-zinc-300 ring-zinc-600/60"
          title={`Phase ${phase}`}
        >
          {phase}
        </span>
      )}
    </div>
  );
}
