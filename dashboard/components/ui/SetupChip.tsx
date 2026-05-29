// Canonical setup_types emitted by the options engine.

const SETUP_STYLES: Record<string, { bg: string; text: string; ring: string }> = {
  MOM_BURST: { bg: "bg-orange-500/15", text: "text-orange-400", ring: "ring-orange-500/30" },
  SQUEEZE:   { bg: "bg-purple-500/15", text: "text-purple-400", ring: "ring-purple-500/30" },
  PULLBACK:  { bg: "bg-cyan-500/15", text: "text-cyan-300", ring: "ring-cyan-500/30" },
  TREND_FLOW: { bg: "bg-emerald-500/15", text: "text-emerald-300", ring: "ring-emerald-500/30" },
};

const FALLBACK = {
  bg: "bg-zinc-500/15",
  text: "text-zinc-400",
  ring: "ring-zinc-500/30",
};

// Map legacy names to canonical so old rows render too.
function canonical(setup: string): string {
  const u = setup.trim().toUpperCase();
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
  return u;
}

export function SetupChip({ setup }: { setup: string | null | undefined }) {
  if (!setup) return <span className="text-zinc-600">—</span>;
  const key = canonical(setup);
  const style = SETUP_STYLES[key] || FALLBACK;
  const label = key === "PULLBACK" ? "Pullback" : key === "TREND_FLOW" ? "Trend Flow" : key.replace("_", " ");
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold tracking-wide ring-1 ring-inset ${style.bg} ${style.text} ${style.ring}`}
    >
      {label}
    </span>
  );
}
