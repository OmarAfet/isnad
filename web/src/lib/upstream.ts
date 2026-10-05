// The browser never talks to the Python service directly. This keeps its address out of the
// client, avoids CORS entirely, and leaves one place to add caching or limits later. The Jev key
// lives with the Python service and never reaches this tier at all.
//
// Deployed, the service has a public address and every search spends the paid Jev key, so it
// serves only callers that present ISNAD_PROXY_SECRET. It sees this tier's address, not the
// reader's, so the reader's address travels in x-isnad-client-ip for its per-minute limit.
export const API = process.env.ISNAD_API_URL ?? "http://localhost:8000";
const SECRET = process.env.ISNAD_PROXY_SECRET ?? "";

export function upstreamHeaders(req: Request): Record<string, string> {
  const client = (req.headers.get("x-forwarded-for") ?? "").split(",")[0].trim();
  return {
    "x-forwarded-for": client,
    "x-isnad-client-ip": client,
    ...(SECRET ? { "x-isnad-proxy": SECRET } : {}),
  };
}
