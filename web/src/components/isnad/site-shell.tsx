import NextLink from "next/link";
import { copy } from "@/lib/copy";

// The wordmark carries a three-link chain, the product's one visual idea in miniature.
export function Wordmark() {
  return (
    <NextLink href="/" className="inline-flex items-center gap-3 rounded-sm focus-visible:outline-2">
      <span aria-hidden className="relative flex h-7 w-2 flex-col items-center justify-between">
        <span className="absolute inset-y-1 w-px bg-primary/40" />
        <span className="relative size-2 rounded-full bg-primary" />
        <span className="relative size-2 rounded-full bg-primary" />
        <span className="relative size-2 rounded-full bg-primary" />
      </span>
      <span className="text-2xl font-bold">{copy.brand}</span>
    </NextLink>
  );
}

export function SiteHeader() {
  return (
    <header className="mx-auto flex w-full max-w-2xl items-center justify-between px-5 pt-8">
      <Wordmark />
      <nav>
        <NextLink
          href="/method"
          className="text-sm text-muted-foreground hover:text-foreground rounded-sm focus-visible:outline-2"
        >
          {copy.nav.method}
        </NextLink>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mx-auto w-full max-w-2xl px-5 pb-10 pt-16">
      <div className="space-y-1.5 border-t pt-6 text-sm text-muted-foreground">
        <p>{copy.footer.ai}</p>
        <p>{copy.footer.rulings}</p>
        <p>{copy.footer.sources}</p>
      </div>
    </footer>
  );
}
