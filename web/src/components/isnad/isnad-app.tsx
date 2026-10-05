"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { copy } from "@/lib/copy";
import type { SearchResponse } from "@/lib/types";
import { ResultView } from "./result-view";
import { SearchForm } from "./search-form";

// Chosen to show what Isnad promises: a paraphrase in Arabic, a fragment of a verse, a
// description in another language, and a widely shared saying that is in fact fabricated (Ibn
// Majah 222, graded mawdu by al-Albani). The last one is the filed idea's stated impact,
// "تقليل تداول الأحاديث الموضوعة", shown rather than claimed.
const EXAMPLES = [
  "حديث عن أن الأعمال بالنيات",
  "الآية اللي فيها لا تأخذه سنة ولا نوم",
  "حديث إن الفقيه أشد على الشيطان من ألف عابد",
  "the hadith about the five pillars of Islam",
];

type State =
  | { status: "idle" }
  | { status: "loading"; q: string }
  | { status: "done"; data: SearchResponse }
  | { status: "error"; message: string };

export function IsnadApp() {
  const router = useRouter();
  const params = useSearchParams();
  const urlQ = params.get("q") ?? "";
  const [state, setState] = useState<State>({ status: "idle" });
  const ran = useRef<string | null>(null);
  const results = useRef<HTMLDivElement>(null);

  const run = useCallback(async (q: string) => {
    ran.current = q;
    setState({ status: "loading", q });
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q }),
      });
      if (res.status === 429) return setState({ status: "error", message: copy.errors.rate });
      if (!res.ok) {
        return setState({
          status: "error",
          message: res.status === 502 ? copy.errors.network : copy.errors.generic,
        });
      }
      const data = (await res.json()) as SearchResponse;
      setState({ status: "done", data });
      requestAnimationFrame(() =>
        results.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    } catch {
      setState({ status: "error", message: copy.errors.network });
    }
  }, []);

  // A result is addressable: ?q= re-runs it, so any answer can be shared and re-tested.
  useEffect(() => {
    if (urlQ && ran.current !== urlQ) void run(urlQ);
  }, [urlQ, run]);

  const onSearch = (q: string) => {
    const sp = new URLSearchParams({ q });
    router.replace(`/?${sp.toString()}`, { scroll: false });
    if (q === urlQ) void run(q);
  };

  return (
    <div className="space-y-12">
      {/* Keyed on the URL query: a shared link or the back button refills the box by remounting
          it, instead of syncing state inside an effect. */}
      <SearchForm
        key={urlQ}
        initial={urlQ}
        busy={state.status === "loading"}
        onSearch={onSearch}
        examples={EXAMPLES}
      />

      <div ref={results} aria-live="polite" className="scroll-mt-8">
        {state.status === "loading" && <LoadingChain q={state.q} />}
        {state.status === "error" && (
          <Alert variant="destructive">
            <AlertCircle className="size-4" />
            <AlertDescription>{state.message}</AlertDescription>
          </Alert>
        )}
        {state.status === "done" && <ResultView data={state.data} onPick={onSearch} />}
      </div>
    </div>
  );
}

function LoadingChain({ q }: { q: string }) {
  return (
    <ol className="relative" aria-busy="true" aria-label={copy.search.submitting}>
      <li className="relative ps-8 pb-7">
        <span aria-hidden className="absolute start-[0.4375rem] top-4 bottom-0 w-px bg-chain" />
        <span aria-hidden className="absolute start-0 top-[0.4rem] size-[0.9375rem] rounded-full bg-foreground ring-4 ring-background" />
        <p className="text-sm text-muted-foreground mb-1.5">{copy.chain.you}</p>
        <p dir="auto" className="text-lg">{q}</p>
      </li>
      {[copy.chain.text, copy.chain.source, copy.chain.ruling].map((label, i) => (
        <li key={label} className="relative ps-8 pb-7 last:pb-0">
          {i < 2 && (
            <span aria-hidden className="absolute start-[0.4375rem] top-4 bottom-0 border-s border-dashed border-chain" />
          )}
          <span aria-hidden className="absolute start-0 top-[0.4rem] size-[0.9375rem] rounded-full bg-muted ring-4 ring-background animate-pulse" />
          <p className="text-sm text-muted-foreground mb-2">{label}</p>
          <Skeleton className={i === 0 ? "h-16 w-full" : "h-6 w-1/2"} />
        </li>
      ))}
    </ol>
  );
}
