import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "إسناد",
    short_name: "إسناد",
    description: "ابحث عن آية أو حديث بالمعنى، واحصل على النص بلفظه ومصدره ودرجته.",
    start_url: "/",
    display: "standalone",
    lang: "ar",
    dir: "rtl",
    background_color: "#f2f4ff",
    theme_color: "#f2f4ff",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}
