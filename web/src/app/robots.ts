import type { MetadataRoute } from "next";

// /api/ returns JSON for the app, not pages, so crawlers skip it.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: "/api/" },
    sitemap: "https://isnad-app.vercel.app/sitemap.xml",
  };
}
