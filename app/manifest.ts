import type { MetadataRoute } from "next";

export const dynamic = "force-static";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/";
const basePath = new URL(siteUrl).pathname.replace(/\/$/, "");

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "The Daily Tape",
    short_name: "Daily Tape",
    description: "Data-first U.S. market intelligence for the latest completed trading session.",
    start_url: `${basePath || ""}/`,
    scope: `${basePath || ""}/`,
    display: "standalone",
    background_color: "#080808",
    theme_color: "#ff5c35",
    icons: [
      { src: `${basePath}/favicon-32x32.png`, sizes: "32x32", type: "image/png" },
      { src: `${basePath}/apple-touch-icon.png`, sizes: "180x180", type: "image/png" },
      { src: `${basePath}/logo.png`, sizes: "512x512", type: "image/png", purpose: "any" },
    ],
  };
}
