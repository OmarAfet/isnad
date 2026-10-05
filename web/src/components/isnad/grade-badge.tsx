import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/types";

// Grade colours carry meaning, so they come from the grade tokens in globals.css and nowhere
// else. Each pair is measured against WCAG AA.
const tone: Record<Severity, string> = {
  sahih: "bg-sahih-tint text-sahih border-sahih/25",
  hasan: "bg-sahih-tint text-sahih border-sahih/25",
  daif: "bg-daif-tint text-daif border-daif/30",
  mawdu: "bg-mawdu-tint text-mawdu border-mawdu/30",
  unknown: "bg-unknown-tint text-unknown border-unknown/25",
  quran: "bg-accent text-foreground border-primary/20",
};

export function GradeBadge({
  severity,
  label,
  className,
}: {
  severity: Severity | null;
  label: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-sm font-medium",
        tone[severity ?? "unknown"],
        className,
      )}
    >
      {label}
    </span>
  );
}

export function dotTone(severity: Severity | null) {
  switch (severity) {
    case "sahih":
    case "hasan":
      return "bg-sahih";
    case "daif":
      return "bg-daif";
    case "mawdu":
      return "bg-mawdu";
    case "quran":
      return "bg-primary";
    default:
      return "bg-unknown";
  }
}
