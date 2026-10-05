import { copy } from "@/lib/copy";

// Jev's confidence, labelled as what it is: how well the text matches the description. It is not
// a judgment of authenticity, and the label and the line under it both say so.
export function MatchMeter({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  // The explanation is always on screen: as a hover tooltip it never opened on a phone or by
  // click (judge-style test, 2026-10-06), and it is the one line that keeps the number honest.
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground shrink-0">{copy.chain.match}</span>
        <div
          className="h-1.5 w-28 rounded-full bg-muted overflow-hidden"
          role="meter"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-label={copy.chain.match}
          aria-describedby="match-help"
        >
          <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
        </div>
        <bdi className="text-sm font-medium tabular-nums">{pct}%</bdi>
      </div>
      <p id="match-help" className="text-xs text-muted-foreground">{copy.chain.matchHelp}</p>
    </div>
  );
}
