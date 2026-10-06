import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: "https://isnad-app.vercel.app", changeFrequency: "weekly", priority: 1 },
    { url: "https://isnad-app.vercel.app/method", changeFrequency: "monthly", priority: 0.7 },
  ];
}
