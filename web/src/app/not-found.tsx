import Link from "next/link";
import { SiteFooter, SiteHeader } from "@/components/isnad/site-shell";
import { copy } from "@/lib/copy";

// The default 404 was Next.js's English page with no way back (judge-style test, 2026-10-06).
export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-2xl flex-1 px-5 pt-16">
        <h1 className="text-3xl font-bold leading-tight">{copy.notFound.title}</h1>
        <p className="mt-4 text-lg text-muted-foreground">{copy.notFound.body}</p>
        <Link href="/" className="mt-8 inline-block text-primary hover:underline">
          {copy.notFound.home}
        </Link>
      </main>
      <SiteFooter />
    </>
  );
}
