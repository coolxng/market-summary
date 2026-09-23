import type { MetadataRoute } from "next";
import { assetCatalog } from "./lib/assets";
import { archivedDates } from "./lib/archive";

export const dynamic = "force-static";

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");
export default function sitemap(): MetadataRoute.Sitemap {
  const reports: MetadataRoute.Sitemap = [...archivedDates()].reverse().map((date) => ({
    url: `${siteUrl}/reports/${date}/`,
    changeFrequency: "never",
    priority: 0.7,
  }));

  const assets: MetadataRoute.Sitemap = [{ url: `${siteUrl}/assets/`, changeFrequency: "daily", priority: 0.8 }, ...assetCatalog.map((asset) => ({
    url: `${siteUrl}/assets/${asset.slug}/`,
    changeFrequency: "daily" as const,
    priority: 0.6,
  }))];

  return [
    {
      url: `${siteUrl}/`,
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${siteUrl}/morning/`,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${siteUrl}/reports/`,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/search/`,
      changeFrequency: "weekly",
      priority: 0.5,
    },
    ...assets,
    ...reports,
  ];
}
