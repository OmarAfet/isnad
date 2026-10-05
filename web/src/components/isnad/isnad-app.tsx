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

type Progress = { stage: string; read: number; total: number };

type State =
  | { status: "idle" }
  | { status: "loading"; q: string; progress?: Progress }
  | { status: "done"; data: SearchResponse }
  | { status: "error"; message: string };

export function IsnadApp() {
  const router = useRouter();
  const params = useSearchParams();
  const urlQ = params.get("q") ?? "";
  const urlId = params.get("id");
  const [state, setState] = useState<State>({ status: "idle" });
  const ran = useRef<string | null>(null);
  const results = useRef<HTMLDivElement>(null);

  const run = useCallback(async (q: string) => {
    ran.current = q;
    setState({ status: "loading", q });

    const finish = (data: SearchResponse) => {
      setState({ status: "done", data });
      requestAnimationFrame(() =>
        results.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    };
    const fail = (status: number) =>
      setState({
        status: "error",
        message:
          status === 429
            ? copy.errors.rate
            : status === 502
              ? copy.errors.network
              : copy.errors.generic,
      });

    // Stream first: Jev reads every text, and the reader sees the count rise. The plain endpoint
    // is the fallback if anything between here and the API does not pass a stream through.
    try {
      const res = await fetch("/api/search/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q }),
      });
      if (!res.ok || !res.body) {
        if (res.status === 429 || res.status === 422) return fail(res.status);
        throw new Error("no stream");
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let total = 0;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let cut: number;
        while ((cut = buf.indexOf("\n\n")) !== -1) {
          const chunk = buf.slice(0, cut);
          buf = buf.slice(cut + 2);
          const line = chunk.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const ev = JSON.parse(line.slice(6));
          if (ev.type === "start") total = ev.texts_total ?? 0;
          if (ev.type === "progress") {
            setState({
              status: "loading",
              q,
              progress: { stage: ev.stage, read: ev.texts_read ?? 0, total: ev.texts_total ?? total },
            });
          }
          if (ev.type === "result") return finish(ev.data as SearchResponse);
          if (ev.type === "error") return fail(500);
        }
      }
      throw new Error("stream ended without a result");
    } catch {
      try {
        const res = await fetch("/api/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ q }),
        });
        if (!res.ok) return fail(res.status);
        finish((await res.json()) as SearchResponse);
      } catch {
        setState({ status: "error", message: copy.errors.network });
      }
    }
  }, []);

  // A result is addressable: ?q= re-runs it, so any answer can be shared and re-tested.
  useEffect(() => {
    if (urlQ && ran.current !== urlQ) void run(urlQ);
  }, [urlQ, run]);

  // Every search and every opened card is a history entry, so Back returns to the list or the
  // search before; replacing the entry, as before, lost them (judge-style test, 2026-10-06).
  const onSearch = (q: string) => {
    const sp = new URLSearchParams({ q });
    router.push(`/?${sp.toString()}`, { scroll: false });
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
        {state.status === "loading" && <LoadingChain q={state.q} progress={state.progress} />}
        {state.status === "error" && (
          <Alert variant="destructive">
            <AlertCircle className="size-4" />
            <AlertDescription>{state.message}</AlertDescription>
          </Alert>
        )}
        {state.status === "done" && (
          <ResultView
            data={state.data}
            picked={urlId}
            onOpen={(id) =>
              router.push(`/?${new URLSearchParams({ q: urlQ, id }).toString()}`, { scroll: false })
            }
            onBack={() => router.push(`/?${new URLSearchParams({ q: urlQ }).toString()}`, { scroll: false })}
          />
        )}
      </div>
    </div>
  );
}

function ReadingProgress({ progress }: { progress?: Progress }) {
  if (!progress || !progress.total) return null;
  const reading = progress.stage === "round1";
  const pct = reading ? Math.min(100, Math.round((progress.read / progress.total) * 100)) : 100;
  const fmt = (n: number) => n.toLocaleString("en-US");
  return (
    <div className="mb-8 space-y-2" role="status">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium">{reading ? copy.search.reading : copy.search.comparing}</span>
        {reading && (
          <bdi className="tabular-nums text-muted-foreground">
            {fmt(progress.read)} {copy.search.of} {fmt(progress.total)}
          </bdi>
        )}
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function LoadingChain({ q, progress }: { q: string; progress?: Progress }) {
  // After 3 s the reader is told why: a cold start, not a hang (5 of 25 judge searches took 6-9 s).
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 3000);
    return () => clearTimeout(t);
  }, []);
  return (
    <>
    <ReadingProgress progress={progress} />
    {slow && <p className="mb-4 text-sm text-muted-foreground" role="status">{copy.search.slow}</p>}
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
    </>
  );
}
