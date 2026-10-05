import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { copy } from "@/lib/copy";

// Jev's confidence, labelled as what it is: how well the text matches the description. It is not
// a judgment of authenticity, and the label and tooltip both say so.
export function MatchMeter({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-muted-foreground shrink-0">{copy.chain.match}</span>
      <div
        className="h-1.5 w-28 rounded-full bg-muted overflow-hidden"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label={copy.chain.match}
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      <bdi className="text-sm font-medium tabular-nums">{pct}%</bdi>
      <Tooltip>
        <TooltipTrigger
          className="text-muted-foreground hover:text-foreground rounded-sm focus-visible:outline-2"
          aria-label={copy.chain.matchHelp}
        >
          <Info className="size-4" />
        </TooltipTrigger>
        <TooltipContent className="max-w-60 text-sm">{copy.chain.matchHelp}</TooltipContent>
      </Tooltip>
    </div>
  );
}
