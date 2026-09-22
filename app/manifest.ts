import type { MetadataRoute } from "next";
import { THEME_COLORS } from "./lib/theme";

export const dynamic = "force-static";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? new URL(siteUrl).pathname.replace(/\/$/, "");

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: `${basePath}/`,
    name: "The Daily Tape",
    short_name: "Daily Tape",
    description: "Data-first U.S. market intelligence: the Morning Tape before the open and the Close Tape after the bell.",
    start_url: `${basePath}/`,
    scope: `${basePath}/`,
    display: "standalone",
    orientation: "any",
    background_color: THEME_COLORS.paper,
    theme_color: THEME_COLORS.paper,
    categories: ["finance", "news"],
    icons: [
      { src: `${basePath}/icon-192.png`, sizes: "192x192", type: "image/png", purpose: "any" },
      { src: `${basePath}/icon-512.png`, sizes: "512x512", type: "image/png", purpose: "any" },
      { src: `${basePath}/icon-maskable-512.png`, sizes: "512x512", type: "image/png", purpose: "maskable" },
      { src: `${basePath}/apple-touch-icon.png`, sizes: "180x180", type: "image/png" },
    ],
    shortcuts: [
      { name: "Morning Tape", short_name: "Morning", url: `${basePath}/morning/` },
      { name: "Report archive", short_name: "Archive", url: `${basePath}/reports/` },
    ],
  };
}
