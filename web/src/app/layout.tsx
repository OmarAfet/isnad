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

export const metadata: Metadata = {
  title: "إسناد",
  description: "صف ما تتذكره من آية أو حديث، واحصل على النص بلفظه ومصدره ودرجته.",
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
        <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
        <Toaster position="bottom-center" dir="rtl" />
      </body>
    </html>
  );
}
