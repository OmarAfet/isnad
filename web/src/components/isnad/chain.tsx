import { cn } from "@/lib/utils";

// The spine. One vertical line on the start edge, with a dot per link. It is the page's single
// structural device: description, text, source, ruling, in that order, which is the order in
// which a reader would verify a citation by hand.

export function Chain({ children, className }: { children: React.ReactNode; className?: string }) {
  return <ol className={cn("relative", className)}>{children}</ol>;
}

export function Link({
  label,
  dot = "bg-primary",
  last = false,
  broken = false,
  children,
}: {
  label: string;
  dot?: string;
  last?: boolean;
  broken?: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className="relative ps-8 pb-7 last:pb-0">
      {!last && (
        <span
          aria-hidden
          className={cn(
            "absolute start-[0.4375rem] top-4 bottom-0 w-px",
            broken ? "border-s border-dashed border-chain" : "bg-chain",
          )}
        />
      )}
      <span
        aria-hidden
        className={cn(
          "absolute start-0 top-[0.4rem] size-[0.9375rem] rounded-full ring-4 ring-background",
          dot,
        )}
      />
      <p className="text-sm text-muted-foreground mb-1.5">{label}</p>
      <div>{children}</div>
    </li>
  );
}
