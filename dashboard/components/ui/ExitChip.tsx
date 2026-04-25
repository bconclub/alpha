// GPFC #54: 15 canonical exit reasons. One chip per row.
// Engine emits these; trade_executor.py + backfill_exit_reasons.py
// fold legacy names (OPT_HARD_SL, RECONCILE_ORPHAN_CLOSED, ...) into
// these short names, so historical rows render the same as new rows.

const EXIT_STYLES: Record<string, { bg: string; text: string; ring: string }> = {
  // Wins / neutral (green)
  TRAIL:   { bg: "bg-emerald-500/15", text: "text-emerald-400", ring: "ring-emerald-500/30" },
  PEAK:    { bg: "bg-emerald-500/15", text: "text-emerald-400", ring: "ring-emerald-500/30" },
  RATCHET: { bg: "bg-green-500/15",   text: "text-green-400",   ring: "ring-green-500/30" },
  TP:      { bg: "bg-green-500/20",   text: "text-green-300",   ring: "ring-green-500/40" },

  // Giveback (yellow)
  BLEED: { bg: "bg-amber-500/15", text: "text-amber-400", ring: "ring-amber-500/30" },

  // Losses (red family)
  STOP:    { bg: "bg-red-500/20",    text: "text-red-400",    ring: "ring-red-500/40" },
  STALLED: { bg: "bg-orange-500/15", text: "text-orange-400", ring: "ring-orange-500/30" },
  DEAD:    { bg: "bg-rose-500/15",   text: "text-rose-400",   ring: "ring-rose-500/30" },
  REVERSE: { bg: "bg-pink-500/15",   text: "text-pink-400",   ring: "ring-pink-500/30" },

  // Safety / system (blue / gray / violet / slate)
  TIMEOUT:   { bg: "bg-blue-500/15",   text: "text-blue-400",   ring: "ring-blue-500/30" },
  EXPIRY:    { bg: "bg-cyan-500/15",   text: "text-cyan-400",   ring: "ring-cyan-500/30" },
  GONE:      { bg: "bg-zinc-500/15",   text: "text-zinc-400",   ring: "ring-zinc-500/30" },
  ORPHAN:    { bg: "bg-zinc-500/15",   text: "text-zinc-400",   ring: "ring-zinc-500/30" },
  DUPLICATE: { bg: "bg-zinc-500/15",   text: "text-zinc-400",   ring: "ring-zinc-500/30" },
  MANUAL:    { bg: "bg-violet-500/15", text: "text-violet-400", ring: "ring-violet-500/30" },
  BREAKEVEN: { bg: "bg-slate-500/15",  text: "text-slate-300",  ring: "ring-slate-500/30" },
};

const FALLBACK = {
  bg: "bg-zinc-500/15",
  text: "text-zinc-400",
  ring: "ring-zinc-500/30",
};

export function ExitChip({ exit }: { exit: string | null | undefined }) {
  if (!exit) return <span className="text-zinc-600">—</span>;
  const key = exit.trim().toUpperCase();
  const style = EXIT_STYLES[key] || FALLBACK;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ring-1 ring-inset ${style.bg} ${style.text} ${style.ring}`}
    >
      {key}
    </span>
  );
}
