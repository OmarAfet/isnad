import { Suspense } from "react";
import { IsnadApp } from "@/components/isnad/isnad-app";
import { SiteFooter, SiteHeader } from "@/components/isnad/site-shell";
import { copy } from "@/lib/copy";

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-2xl flex-1 px-5 pt-16">
        <h1 className="text-4xl font-bold leading-tight md:text-5xl">{copy.hero.title}</h1>
        <p className="mt-4 mb-10 text-lg text-muted-foreground">{copy.hero.subtitle}</p>
        <Suspense>
          <IsnadApp />
        </Suspense>
      </main>
      <SiteFooter />
    </>
  );
}
