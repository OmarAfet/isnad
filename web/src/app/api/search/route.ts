import { NextResponse } from "next/server";
import { API, upstreamHeaders } from "@/lib/upstream";

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
        ...upstreamHeaders(req),
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
