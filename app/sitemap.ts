import fs from "node:fs";
import path from "node:path";
import type { MetadataRoute } from "next";
import { assetCatalog } from "./lib/assets";

export const dynamic = "force-static";

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");
const datePattern = /^\d{4}-\d{2}-\d{2}$/;

function archivedReportDates() {
  const reportsDir = path.join(process.cwd(), "public", "reports");
  if (!fs.existsSync(reportsDir)) return [];

  return fs
    .readdirSync(reportsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && datePattern.test(entry.name))
    .filter((entry) => fs.existsSync(path.join(reportsDir, entry.name, "report.json")))
    .map((entry) => entry.name)
    .sort()
    .reverse();
}

export default function sitemap(): MetadataRoute.Sitemap {
  const reports: MetadataRoute.Sitemap = archivedReportDates().map((date) => ({
    url: `${siteUrl}/reports/${date}/`,
    changeFrequency: "never",
    priority: 0.7,
  }));

  const assets: MetadataRoute.Sitemap = assetCatalog.map((asset) => ({
    url: `${siteUrl}/assets/${asset.slug}/`,
    changeFrequency: "daily",
    priority: 0.6,
  }));

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
