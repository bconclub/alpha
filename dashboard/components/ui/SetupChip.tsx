// Canonical setup_types emitted by the options engine.

const SETUP_STYLES: Record<string, { bg: string; text: string; ring: string }> = {
  MOM_BURST: { bg: "bg-orange-500/15", text: "text-orange-400", ring: "ring-orange-500/30" },
  SQUEEZE:   { bg: "bg-purple-500/15", text: "text-purple-400", ring: "ring-purple-500/30" },
  PULLBACK:  { bg: "bg-cyan-500/15", text: "text-cyan-300", ring: "ring-cyan-500/30" },
  TREND_FLOW: { bg: "bg-emerald-500/15", text: "text-emerald-300", ring: "ring-emerald-500/30" },
  PREMIUM_WAVE: { bg: "bg-lime-500/15", text: "text-lime-300", ring: "ring-lime-500/30" },
  FVG_CHOCH: { bg: "bg-sky-500/15", text: "text-sky-300", ring: "ring-sky-500/30" },
  // V3 mirror lanes (short, human names — never the raw lane id)
  MANUAL: { bg: "bg-violet-500/15", text: "text-violet-300", ring: "ring-violet-500/30" },
  DONCHIAN: { bg: "bg-sky-500/15", text: "text-sky-300", ring: "ring-sky-500/30" },
  EMA_PULLBACK: { bg: "bg-cyan-500/15", text: "text-cyan-300", ring: "ring-cyan-500/30" },
  VWAP: { bg: "bg-amber-500/15", text: "text-amber-300", ring: "ring-amber-500/30" },
  LIQ_SWEEP: { bg: "bg-rose-500/15", text: "text-rose-300", ring: "ring-rose-500/30" },
};

const FALLBACK = {
  bg: "bg-zinc-500/15",
  text: "text-zinc-400",
  ring: "ring-zinc-500/30",
};

// Map legacy names to canonical so old rows render too.
function canonical(setup: string): string {
  let u = setup.trim().toUpperCase();
  // Mirror/paper lane ids → short names: strip LIVE_ prefix and lane suffixes.
  if (u.startsWith("LIVE_")) u = u.slice(5);
  if (u.startsWith("FUT_")) {
    if (u.includes("DONCHIAN")) return "DONCHIAN";
    if (u.includes("EMA_PB") || u.includes("EMA_PULLBACK")) return "EMA_PULLBACK";
    if (u.includes("VWAP")) return "VWAP";
    if (u.includes("SFP")) return "LIQ_SWEEP";
  }
  if (u === "BB_SQUEEZE" || u === "BB_SQUEEZE_BREAKOUT" || u === "SQUEEZE_BREAKOUT") {
    return "SQUEEZE";
  }
  if (u === "MOMENTUM_BURST" || u === "MOMENTUM_BURST_ENTRY") {
    return "MOM_BURST";
  }
  if (u === "MOVE_PULLBACK" || u === "PULL_BACK" || u === "PULLBACK") {
    return "PULLBACK";
  }
  if (u === "TREND_FLOW" || u === "TREND") {
    return "TREND_FLOW";
  }
  if (u === "PREMIUM_WAVE" || u === "WAVE") {
    return "PREMIUM_WAVE";
  }
  if (u === "FVG_CHOCH" || u === "FVG_REVERSAL" || u === "FVG_REVERSE") {
    return "FVG_CHOCH";
  }
  return u;
}

export function SetupChip({
  setup,
  secondEntry = false,
}: {
  setup: string | null | undefined;
  secondEntry?: boolean;
}) {
  if (!setup) return <span className="text-zinc-600">—</span>;
  const key = canonical(setup);
  const style = SETUP_STYLES[key] || FALLBACK;
  const LABELS: Record<string, string> = {
    PULLBACK: "Pullback",
    TREND_FLOW: "Trend Flow",
    PREMIUM_WAVE: "Premium Wave",
    FVG_CHOCH: "Zone Pullback",
    DONCHIAN: "Donchian",
    EMA_PULLBACK: "EMA Pullback",
    VWAP: "VWAP",
    LIQ_SWEEP: "Liq Sweep",
    MANUAL: "Manual",
  };
  const label = LABELS[key] ?? key.replace("_", " ");
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold tracking-wide ring-1 ring-inset ${style.bg} ${style.text} ${style.ring}`}
    >
      {label}
      {secondEntry && (
        <span className="rounded bg-amber-400/15 px-1 py-px text-[9px] font-bold uppercase tracking-normal text-amber-300 ring-1 ring-amber-400/30">
          2nd
        </span>
      )}
    </span>
  );
}
