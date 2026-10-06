# Isnad web app

The Next.js interface of Isnad. Setup, sources, licences and results: [../README.md](../README.md).

- Interface copy (white Saudi dialect) lives in `src/lib/copy.ts`; its decisions in `COPY.md`.
- The browser never calls the Python API directly: `src/app/api/*` forwards requests with the
  proxy secret (`ISNAD_API_URL`, `ISNAD_PROXY_SECRET`).

```bash
pnpm install
pnpm dev        # http://localhost:3000, expects the API on http://localhost:8000
```
