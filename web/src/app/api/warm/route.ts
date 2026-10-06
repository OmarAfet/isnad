import { API } from "@/lib/upstream";

// WARM-UP. The first search after a few idle minutes took 7-9 s, nearly all of it the Python
// service starting (judge test, 2026-10-06: 4 of 65 searches). The home page calls this once on
// load, so the service is up by the time a reader has typed. Health is free: no Jev call, no key.
// POST, because route handlers' GET may be cached and a cached warm-up warms nothing.
export async function POST() {
  try {
    await fetch(`${API}/api/health`, { cache: "no-store", signal: AbortSignal.timeout(20_000) });
  } catch {
    // A failed warm-up changes nothing for the reader: the search itself starts the service.
  }
  return new Response(null, { status: 204 });
}
