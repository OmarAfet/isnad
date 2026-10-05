// Streams the backend's Server-Sent Events straight through. In full-corpus mode Jev reads every
// text, which takes about forty seconds, and the reader is owed the sight of it working: each
// event says how many texts have been read so far.
import { API, upstreamHeaders } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let q = "";
  try {
    const body = (await req.json()) as { q?: unknown };
    q = typeof body.q === "string" ? body.q : "";
  } catch {
    return new Response(JSON.stringify({ error: "bad_request" }), { status: 400 });
  }
  if (q.trim().length < 3 || q.length > 300) {
    return new Response(JSON.stringify({ error: "invalid_query" }), { status: 422 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API}/api/search/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...upstreamHeaders(req),
      },
      body: JSON.stringify({ q }),
      cache: "no-store",
      signal: AbortSignal.timeout(240_000),
    });
  } catch {
    return new Response(JSON.stringify({ error: "upstream_unreachable" }), { status: 502 });
  }
  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text(), { status: upstream.status });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
