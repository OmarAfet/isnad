"use client";

import { useRef, useState } from "react";
import { Languages, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

export function SearchForm({
  initial,
  busy,
  onSearch,
  examples,
}: {
  initial: string;
  busy: boolean;
  onSearch: (q: string) => void;
  examples: string[];
}) {
  const [q, setQ] = useState(initial);
  const [warn, setWarn] = useState<string | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);

  const submit = (value: string) => {
    const v = value.trim();
    if (v.split(/\s+/).filter(Boolean).length < 2) {
      setWarn(copy.search.tooShort);
      ref.current?.focus();
      return;
    }
    setWarn(null);
    onSearch(v);
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit(q);
      }}
      className="space-y-3"
    >
      <label htmlFor="q" className="sr-only">
        {copy.search.label}
      </label>
      <Textarea
        id="q"
        ref={ref}
        dir="auto"
        rows={3}
        value={q}
        maxLength={300}
        onChange={(e) => {
          setQ(e.target.value);
          // The "too short" warning goes as soon as it no longer applies; it used to stay on a
          // 60-word description until the next search (judge-style test, 2026-10-06).
          if (warn === copy.search.tooShort && e.target.value.trim().split(/\s+/).length >= 2) {
            setWarn(null);
          }
        }}
        onPaste={(e) => {
          // The box holds 300 characters; a longer paste is cut, and the reader is told so.
          const el = e.currentTarget;
          const room = 300 - (q.length - ((el.selectionEnd ?? 0) - (el.selectionStart ?? 0)));
          if (e.clipboardData.getData("text").length > room) setWarn(copy.search.tooLong);
        }}
        onKeyDown={(e) => {
          // Enter searches; Shift+Enter adds a line for longer descriptions.
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit(q);
          }
        }}
        placeholder={copy.search.placeholder}
        aria-describedby="q-hint"
        aria-invalid={!!warn}
        className="min-h-24 resize-none bg-card text-lg leading-relaxed p-4 shadow-sm"
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p
          id="q-hint"
          className={cn(
            "flex items-center gap-1.5 text-sm",
            warn === copy.search.tooShort ? "text-destructive" : "text-muted-foreground",
          )}
        >
          <Languages className="size-4" />
          {warn ?? copy.search.hint}
        </p>
        <Button type="submit" size="lg" disabled={busy} className="min-w-36">
          {busy ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
          {busy ? copy.search.submitting : copy.search.submit}
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <span className="text-sm text-muted-foreground">{copy.search.tryLabel}:</span>
        {examples.map((ex) => (
          <Button
            key={ex}
            type="button"
            variant="secondary"
            size="sm"
            disabled={busy}
            onClick={() => {
              setQ(ex);
              submit(ex);
            }}
            className="font-normal"
          >
            <bdi>{ex}</bdi>
          </Button>
        ))}
      </div>
    </form>
  );
}
