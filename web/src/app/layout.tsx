import type { Metadata, Viewport } from "next";
import { Amiri, Amiri_Quran, Readex_Pro } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

// Readex Pro is the challenge's brand face, so the app and the deck read as one submission.
const readex = Readex_Pro({
  variable: "--font-readex",
  subsets: ["arabic", "latin"],
  display: "swap",
});

// Scripture gets its own naskh faces. Amiri Quran carries the Uthmani marks the King Fahd
// Complex text uses; Amiri sets the fully vocalized hadith text.
const amiri = Amiri({
  variable: "--font-amiri",
  subsets: ["arabic"],
  weight: ["400", "700"],
  display: "swap",
});

const amiriQuran = Amiri_Quran({
  variable: "--font-amiri-quran",
  subsets: ["arabic"],
  weight: "400",
  display: "swap",
});

// A shared link previews as what it is (judge-style test: a shared ?q= link had no preview).
// The title carries the search words people type ("آية", "حديث", "تخريج") because the bare
// brand name matched no query.
const SITE_URL = "https://isnad-app.vercel.app";
const TITLE = "إسناد: ابحث عن آية أو حديث بالمعنى";
const DESCRIPTION =
  "صف ما تتذكره من آية أو حديث بأي لغة، واحصل على النص بلفظه ومصدره ودرجته من القرآن الكريم والصحيحين والسنن الأربع.";
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: TITLE, template: "%s | إسناد" },
  description: DESCRIPTION,
  applicationName: "إسناد",
  keywords: [
    "البحث عن حديث",
    "البحث عن آية",
    "تخريج الحديث",
    "درجة الحديث",
    "صحيح البخاري",
    "صحيح مسلم",
    "القرآن الكريم",
    "hadith search",
    "Quran verse finder",
  ],
  alternates: { canonical: "/" },
  robots: { index: true, follow: true },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: "/",
    siteName: "إسناد",
    locale: "ar_SA",
    type: "website",
  },
  twitter: { card: "summary", title: TITLE, description: DESCRIPTION },
};

// ?q= re-runs a search, so search engines can offer a site search box.
const JSON_LD = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "إسناد",
  url: SITE_URL,
  inLanguage: "ar",
  description: DESCRIPTION,
  potentialAction: {
    "@type": "SearchAction",
    target: `${SITE_URL}/?q={search_term_string}`,
    "query-input": "required name=search_term_string",
  },
};

export const viewport: Viewport = {
  themeColor: "#f2f4ff",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="ar"
      dir="rtl"
      className={`${readex.variable} ${amiri.variable} ${amiriQuran.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
        />
        <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
        <Toaster position="bottom-center" dir="rtl" />
      </body>
    </html>
  );
}
