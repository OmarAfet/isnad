import { NextResponse } from "next/server";

// The browser never talks to the Python service directly. This keeps its address out of the
// client, avoids CORS entirely, and leaves one place to add caching or limits later. The Jev key
// lives with the Python service and never reaches this tier at all.
const API = process.env.ISNAD_API_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  const q = typeof (body as { q?: unknown })?.q === "string" ? (body as { q: string }).q : "";
  if (q.trim().length < 3 || q.length > 300) {
    return NextResponse.json({ error: "invalid_query" }, { status: 422 });
  }

  try {
    const res = await fetch(`${API}/api/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-forwarded-for": req.headers.get("x-forwarded-for") ?? "",
      },
      body: JSON.stringify({ q }),
      signal: AbortSignal.timeout(30_000),
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({ error: "bad_upstream" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "upstream_unreachable" }, { status: 502 });
  }
}
