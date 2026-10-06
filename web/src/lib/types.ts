// Mirrors api/app.py. Field names are a contract: the API returns codes, the web app owns copy.

export type Verdict =
  | "confident"
  | "tentative"
  | "unsure"
  | "no_match"
  | "topic"
  | "ruling"
  | "question"        // a question about Islam, not a ruling: texts that speak to it + a reference
  | "out_of_scope"    // outside Isnad's work (judging people or groups): said plainly, no texts
  | "fatwa_request"   // knockout mode only: a referral with no texts (session-1 behaviour)
  | "decision_unavailable";

// A question about a ruling. Isnad answers it with the texts on the matter and a referral, never
// with a ruling of its own. "personal": the asker's own case (Reference Framework level د).
export interface RulingInfo {
  kind: "general" | "personal";
  fiqh_url: string;
}

export type Severity = "sahih" | "hasan" | "daif" | "mawdu" | "unknown" | "quran";

export interface Grader {
  grader: string;
  grade: string;
}

export interface Variant {
  id: string;
  ref: string;
  grade: string | null;
}

export interface Translation {
  lang: string;
  text: string;
  translator: string | null;
  edition: string | null;
}

export interface TextRecord {
  id: string;
  kind: "ayah" | "hadith";
  ref: string;
  collection: string | null;
  surah_name: string | null;
  ayah: number | null;
  number: number | string | null;
  matn: string;
  sanad: string | null;
  commentary?: string | null;
  grade: string | null;
  grade_basis: "quran" | "inherent" | "cited" | "none" | null;
  severity: Severity | null;
  action: string | null;
  scope: string | null;
  graders: Grader[];
  variants: Variant[];
  translation: Translation | null;
  matched_language: string | null;
  verify_url: string | null;
  probability?: number;
  relevance?: number;
}

export interface SearchResponse {
  query: string;
  query_language: string | null;
  verdict: Verdict;
  confidence: number | null;
  specific_enough: number | null;
  result: TextRecord | null;
  alternatives: TextRecord[];
  topic?: TextRecord[];
  ruling?: RulingInfo | null;
  // A surah named on its own ("سورة الإخلاص"): its verses, in order, looked up rather than judged.
  surah?: { name: string; verses: number } | null;
  // A question about Islam: the kind of approved reference that answers it, and its address.
  refer?: { kind: string; url: string } | null;
  scope?: "judge_people" | null;
  // Positions in query.split(" ") of quoted words the text does not have.
  wording?: { missing: number[] } | null;
  // A citation looked up by its reference, not searched: no match percentage applies.
  lookup?:
    | { kind: "ayah"; surah: string; from: number; to: number }
    | { kind: "hadith"; ref: string; count: number }
    | null;
  jev?: { rounds: number; net: number; groups: number };
  timing_ms: { search: number; decide: number | null; total: number };
  cached?: boolean;
  error?: string;
}
