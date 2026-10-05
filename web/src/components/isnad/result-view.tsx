"use client";

import { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleSlash,
  ListTree,
  Copy,
  ExternalLink,
  OctagonAlert,
  Scale,
} from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { copy, langName, ltrLangs, translatorAr } from "@/lib/copy";
import type { SearchResponse, TextRecord } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Chain, Link } from "./chain";
import { GradeBadge, dotTone } from "./grade-badge";
import { MatchMeter } from "./match-meter";

export function ResultView({
  data,
  picked,
  onOpen,
  onBack,
}: {
  data: SearchResponse;
  picked?: string | null;
  onOpen?: (id: string) => void;
  onBack?: () => void;
}) {
  const { verdict, result } = data;

  // The chain always starts with what the reader wrote, so every outcome, including silence,
  // is shown against the description it answers.
  const describe = (hasText: boolean) => (
    <Link label={copy.chain.you} dot="bg-foreground" last={!hasText} broken={!hasText}>
      <p dir="auto" className="text-lg leading-relaxed">{data.query}</p>
    </Link>
  );
  const description = describe(!!result);

  // A text opened from a list is shown from the answer already in hand, under the reader's own
  // description. Re-searching the card's text, as before, opened Muslim 176 for a click on Muslim
  // 175 and put the card's text in place of what the reader wrote (judge-style test, 2026-10-06).
  const opened = picked ? (data.topic ?? []).find((t) => t.id === picked) : undefined;
  if (opened) {
    return (
      <div className="space-y-6">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline rounded-sm focus-visible:outline-2"
        >
          <ChevronRight className="size-4" />
          {copy.verdict.backToList}
        </button>
        <TextChain r={opened} description={describe(true)} />
        <Actions r={opened} />
      </div>
    );
  }

  // A ruling question gets the texts on the matter and a referral, never a ruling: Reference
  // Framework level (د), "يوضح المعلومات العامة ويحيل إلى جهة مؤهلة".
  if (verdict === "ruling") {
    const personal = data.ruling?.kind === "personal";
    const texts = data.topic ?? [];
    return (
      <div className="space-y-5">
        <Chain>
          {description}
          <Terminal
            icon={<Scale className="size-5" />}
            text={personal ? copy.ruling.personal : texts.length ? copy.ruling.general : copy.ruling.none}
            sub={personal && texts.length ? copy.ruling.personalTexts : undefined}
          />
        </Chain>
        {texts.length > 0 && (
          <ul className="space-y-3">
            {texts.map((t) => (
              <li key={t.id}>
                <TopicCard record={t} onOpen={onOpen} />
              </li>
            ))}
          </ul>
        )}
        <Referral url={data.ruling?.fiqh_url} />
      </div>
    );
  }

  if (verdict === "fatwa_request") {
    return (
      <Chain>
        {description}
        <Terminal icon={<Scale className="size-5" />} text={copy.verdict.fatwa} />
      </Chain>
    );
  }

  if (verdict === "topic" && data.topic?.length) {
    const lead = data.surah
      ? data.surah.verses <= data.topic.length
        ? copy.verdict.surahAll(data.surah.name)
        : copy.verdict.surahFirst(data.surah.name, data.topic.length, data.surah.verses)
      : data.topic.length === 1
        ? copy.verdict.topicOne
        : copy.verdict.topic;
    return (
      <div className="space-y-5">
        <Chain>
          {description}
          <Terminal icon={<ListTree className="size-5" />} text={lead} />
        </Chain>
        <ul className="space-y-3">
          {data.topic.map((t) => (
            <li key={t.id}>
              <TopicCard record={t} onOpen={onOpen} />
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (verdict === "no_match" || verdict === "topic" || (!result && verdict !== "decision_unavailable")) {
    // "Not found" says what happened in every case. The hint to add wording is only a hint: for
    // an exact saying that is simply not in the books ("حب الوطن من الإيمان"), "we could not tell
    // which text you mean" was false. A dorar search is the next step a reader can take.
    const vague = (data.specific_enough ?? 1) < 0.35;
    return (
      <div className="space-y-5">
        <Chain>
          {description}
          <Terminal
            icon={<CircleSlash className="size-5" />}
            text={copy.verdict.noMatch}
            sub={vague ? copy.verdict.noMatchVague : undefined}
          />
        </Chain>
        {data.query_language === "ar" && (
          <Button variant="outline" size="sm" asChild>
            <a href={dorarSearch(data.query)} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="size-4" />
              {copy.verdict.searchDorar}
            </a>
          </Button>
        )}
      </div>
    );
  }

  if (verdict === "decision_unavailable") {
    return (
      <div className="space-y-5">
        <Chain>{description}</Chain>
        <Alert>
          <AlertTriangle className="size-4" />
          <AlertDescription>{copy.verdict.unavailable}</AlertDescription>
        </Alert>
        <Alternatives items={data.alternatives} />
      </div>
    );
  }

  const r = result!;
  return (
    <div className="space-y-6">
      {/* Unsure means the text may not be the one meant: that is said before the text, not
          after it. A judge read a sound hadith offered for "النظافة من الإيمان" as the answer. */}
      {verdict === "unsure" && <Caution text={copy.verdict.unsure} />}
      <TextChain r={r} description={description} />
      {verdict === "tentative" && <Caution text={copy.verdict.tentative} />}
      <Actions r={r} confidence={data.confidence} />
      {verdict !== "confident" && <Alternatives items={data.alternatives} />}
    </div>
  );
}

function dorarSearch(q: string) {
  return `https://dorar.net/hadith/search?q=${encodeURIComponent(q)}`;
}

function Caution({ text }: { text: string }) {
  return (
    <p className="flex items-start gap-2 text-sm text-daif">
      <AlertTriangle className="size-4 mt-1 shrink-0" />
      <span>{text}</span>
    </p>
  );
}

function TextChain({ r, description }: { r: TextRecord; description: React.ReactNode }) {
  // A verse needs no grading row: "الحكم: قرآن كريم" read oddly, and the source says what it is.
  const isAyah = r.kind === "ayah";
  // Muslim's sub-narrations share Abd al-Baqi's number ("صحيح مسلم (16)" twice): each reference
  // is listed once, and never the reference already shown as the source.
  const variants = r.variants.filter(
    (v, i, all) => v.ref !== r.ref && all.findIndex((w) => w.ref === v.ref) === i,
  );
  return (
    <Chain>
      {description}

      <Link label={copy.chain.text} dot={dotTone(r.severity)}>
        <Scripture record={r} />
        {r.translation && <TranslationBlock t={r.translation} />}
      </Link>

      <Link label={copy.chain.source} dot={dotTone(r.severity)} last={isAyah}>
        <p className="text-lg font-medium">
          <bdi>{r.ref}</bdi>
        </p>
        {variants.length > 0 && (
          <p className="mt-1 text-sm text-muted-foreground">
            {copy.chain.alsoIn}:{" "}
            {/* Each copy carries its own grade: the same report can be graded differently in
                another collection, and hiding that would overstate the chosen copy's standing. */}
            {variants.map((v, i) => (
              <span key={v.id}>
                <bdi>{v.ref}</bdi>
                {v.grade && v.grade !== r.grade ? <span> ({v.grade})</span> : null}
                {i < variants.length - 1 ? "، " : ""}
              </span>
            ))}
          </p>
        )}
        {r.sanad && <Sanad text={r.sanad} />}
        {r.commentary && <Note label={copy.chain.commentary} text={r.commentary} />}
      </Link>

      {!isAyah && (
        <Link label={copy.chain.ruling} dot={dotTone(r.severity)} last>
          <Ruling record={r} />
        </Link>
      )}
    </Chain>
  );
}

function Actions({ r, confidence }: { r: TextRecord; confidence?: number | null }) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t pt-5">
      {confidence != null && <MatchMeter value={confidence} />}
      <div className="flex flex-wrap gap-2 ms-auto">
        <CopyButton record={r} />
        {r.verify_url && (
          <Button variant="outline" size="sm" asChild>
            <a href={r.verify_url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="size-4" />
              {copy.chain.verify}
            </a>
          </Button>
        )}
      </div>
    </div>
  );
}

function Scripture({ record }: { record: TextRecord }) {
  const isAyah = record.kind === "ayah";
  return (
    <blockquote
      className={cn(
        isAyah ? "quran text-[1.65rem]" : "scripture text-[1.4rem]",
        "text-foreground",
      )}
    >
      {isAyah ? <>﴿{record.matn}﴾</> : record.matn}
    </blockquote>
  );
}

function TranslationBlock({ t }: { t: NonNullable<TextRecord["translation"]> }) {
  const ltr = ltrLangs.has(t.lang);
  return (
    <figure className="mt-4 rounded-lg bg-muted/60 p-4">
      <figcaption className="mb-2 text-xs text-muted-foreground">
        {copy.chain.translation} ({langName[t.lang] ?? t.lang})،{" "}
        {t.translator ? (
          <bdi>{copy.chain.translator(translatorAr[t.translator] ?? t.translator)}</bdi>
        ) : (
          copy.chain.translatorUnknown
        )}
      </figcaption>
      <p dir={ltr ? "ltr" : "rtl"} lang={t.lang} className="text-[0.95rem] leading-relaxed">
        {t.text}
      </p>
    </figure>
  );
}

function Sanad({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-2">
      <CollapsibleTrigger className="inline-flex items-center gap-1 text-sm text-primary hover:underline rounded-sm focus-visible:outline-2">
        {open ? copy.chain.hideSanad : copy.chain.showSanad}
        <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <p className="scripture mt-2 text-base leading-loose text-muted-foreground">{text}</p>
      </CollapsibleContent>
    </Collapsible>
  );
}

// The compiler's own words after the hadith, for example al-Tirmidhi's "هذا حديث حسن". Kept
// apart from the text so they are never read as the Prophet's words, and shown on request because
// they often carry the compiler's own grading.
function Note({ label, text }: { label: string; text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-1">
      <CollapsibleTrigger className="inline-flex items-center gap-1 text-sm text-primary hover:underline rounded-sm focus-visible:outline-2">
        {label}
        <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <p className="scripture mt-2 text-base leading-loose text-muted-foreground">{text}</p>
      </CollapsibleContent>
    </Collapsible>
  );
}

function Ruling({ record }: { record: TextRecord }) {
  const [open, setOpen] = useState(false);
  if (record.kind === "ayah") {
    return <GradeBadge severity="quran" label={copy.grade.quran} />;
  }
  // The grader whose ruling became the label is shown once, by name; "others" are the rest. The
  // warning names that grader instead of "they judged it", which overstated agreement when the
  // others called it only weak (judge-style test, Ibn Majah 222).
  const main = mainGrader(record);
  const others = record.graders.filter((g) => g !== main && g.grade);
  const label = record.grade ?? copy.grade.unknown;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <GradeBadge severity={record.severity} label={label} />
        {record.grade && (
          <span className="text-sm text-muted-foreground">
            {record.grade_basis === "inherent"
              ? `أخرجه ${shortCollection(record.collection)} في صحيحه`
              : graderNote(record)}
          </span>
        )}
      </div>

      {record.severity === "daif" && (
        <Alert className="border-daif/40 bg-daif-tint text-daif">
          <AlertTriangle className="size-4" />
          <AlertDescription className="text-daif">{copy.grade.daif(main?.grader)}</AlertDescription>
        </Alert>
      )}
      {record.severity === "mawdu" && (
        <Alert className="border-mawdu/40 bg-mawdu-tint text-mawdu">
          <OctagonAlert className="size-4" />
          <AlertDescription className="text-mawdu">{copy.grade.mawdu(main?.grader)}</AlertDescription>
        </Alert>
      )}
      {!record.grade && <p className="text-sm text-muted-foreground">{copy.grade.unknown}</p>}

      {others.length > 0 && (
        <Collapsible open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger className="inline-flex items-center gap-1 text-sm text-primary hover:underline rounded-sm focus-visible:outline-2">
            {copy.chain.otherRulings}
            <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <ul className="mt-2 space-y-1.5 text-sm">
              {others.map((g, i) => (
                <li key={i} className="flex flex-wrap gap-x-2">
                  <span className="text-muted-foreground">{g.grader}:</span>
                  <span className="font-medium">{g.grade}</span>
                </li>
              ))}
            </ul>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}

function mainGrader(r: TextRecord) {
  return r.graders.find((x) => x.grade === r.grade) ?? r.graders[0];
}

function graderNote(r: TextRecord) {
  // The grader whose ruling became the label, by name, as the framework requires.
  const g = mainGrader(r);
  return g ? `حكم ${g.grader}` : "";
}

function shortCollection(c: string | null) {
  if (!c) return "";
  return c.replace(/^صحيح\s+/, "");
}

function CopyButton({ record }: { record: TextRecord }) {
  // The copied text always carries its reference and grade, so a citation pasted elsewhere
  // arrives with its source attached.
  const onCopy = async () => {
    const grade = record.kind === "ayah" ? "" : record.grade ? `، ${record.grade}` : "";
    const text = `${record.matn}\n[${record.ref}${grade}]`;
    try {
      await navigator.clipboard.writeText(text);
      toast.success(copy.chain.copied);
    } catch {
      toast.error(copy.errors.generic);
    }
  };
  return (
    <Button variant="outline" size="sm" onClick={onCopy}>
      <Copy className="size-4" />
      {copy.chain.copy}
    </Button>
  );
}

function Terminal({ icon, text, sub }: { icon: React.ReactNode; text: string; sub?: string }) {
  return (
    <li className="relative ps-8 pt-1">
      <span
        aria-hidden
        className="absolute start-0 top-1.5 grid size-[0.9375rem] place-items-center rounded-full border-2 border-chain bg-background"
      />
      <div className="flex items-start gap-2 text-foreground">
        <span className="mt-0.5 text-muted-foreground">{icon}</span>
        <div>
          <p className="text-lg font-medium">{text}</p>
          {sub && <p className="mt-1 text-muted-foreground">{sub}</p>}
        </div>
      </div>
    </li>
  );
}

function Alternatives({ items }: { items: TextRecord[] }) {
  if (!items?.length) return null;
  return (
    <section className="space-y-3">
      <h3 className="text-sm text-muted-foreground">{copy.chain.alternatives}</h3>
      <ul className="space-y-3">
        {items.map((a) => (
          <li key={a.id} className="rounded-lg border bg-card p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
              <bdi className="font-medium">{a.ref}</bdi>
              {a.kind === "ayah" ? (
                <GradeBadge severity="quran" label={copy.grade.quran} />
              ) : (
                a.grade && <GradeBadge severity={a.severity} label={a.grade} />
              )}
              {a.probability != null && (
                <bdi className="ms-auto text-muted-foreground tabular-nums">
                  {Math.round(a.probability * 100)}%
                </bdi>
              )}
            </div>
            <p className={cn(a.kind === "ayah" ? "quran" : "scripture", "text-lg line-clamp-2")}>
              {a.matn}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Referral({ url }: { url?: string | null }) {
  return (
    <aside className="space-y-2 rounded-lg border bg-card p-4">
      <p className="flex items-center gap-2 text-lg font-medium">
        <Scale className="size-5 text-muted-foreground" />
        {copy.ruling.noFatwa}
      </p>
      <p className="text-muted-foreground">{copy.ruling.detail}</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {url && (
          <Button variant="outline" size="sm" asChild>
            <a href={url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="size-4" />
              {copy.ruling.fiqh}
            </a>
          </Button>
        )}
        <span>{copy.ruling.ask}</span>
      </div>
    </aside>
  );
}

function TopicCard({ record: t, onOpen }: { record: TextRecord; onOpen?: (id: string) => void }) {
  const isAyah = t.kind === "ayah";
  // Opening a card shows that text in the full chain view: source, ruling, every named grader,
  // variants and the dorar link, from the answer already in hand.
  return (
    <button
      type="button"
      onClick={() => onOpen?.(t.id)}
      aria-label={`${copy.verdict.topicOpen}: ${t.ref}`}
      className="group w-full rounded-lg border bg-card p-4 text-start transition-colors hover:border-primary/50 focus-visible:outline-2 focus-visible:outline-ring"
    >
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <bdi className="font-medium">{t.ref}</bdi>
        {isAyah ? (
          <GradeBadge severity="quran" label={copy.grade.quran} />
        ) : (
          <GradeBadge severity={t.severity} label={t.grade ?? copy.grade.unknown} />
        )}
        <ChevronLeft className="ms-auto size-4 text-muted-foreground transition-transform group-hover:-translate-x-0.5" />
      </div>
      <p className={cn(isAyah ? "quran" : "scripture", "text-lg line-clamp-3")}>{t.matn}</p>
    </button>
  );
}
