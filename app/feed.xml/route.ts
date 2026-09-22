import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-static";

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");
const datePattern = /^\d{4}-\d{2}-\d{2}$/;

function escapeXml(value: string) {
  return value.replace(/[<>&'"]/g, (character) => ({
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "'": "&apos;",
    '"': "&quot;",
  })[character] ?? character);
}

export function GET() {
  const reportsDir = path.join(process.cwd(), "public", "reports");
  const items: Array<{ date: string; headline: string }> = [];

  if (fs.existsSync(reportsDir)) {
    for (const entry of fs.readdirSync(reportsDir, { withFileTypes: true })) {
      if (!entry.isDirectory() || !datePattern.test(entry.name)) continue;
      const file = path.join(reportsDir, entry.name, "report.json");
      if (!fs.existsSync(file)) continue;
      try {
        const report = JSON.parse(fs.readFileSync(file, "utf8")) as {
          narrative?: { editorial?: { headline?: string }; daily_takeaway?: { what_moved?: string } };
        };
        items.push({
          date: entry.name,
          headline: report.narrative?.editorial?.headline ?? report.narrative?.daily_takeaway?.what_moved ?? "Daily market close",
        });
      } catch {
        // A malformed archive should not prevent the rest of the feed from building.
      }
    }
  }

  items.sort((a, b) => b.date.localeCompare(a.date));
  const xmlItems = items.slice(0, 30).map((item) => {
    const url = `${siteUrl}/reports/${item.date}/`;
    const pubDate = new Date(`${item.date}T21:00:00Z`).toUTCString();
    return `<item><title>${escapeXml(item.headline)}</title><link>${url}</link><guid isPermaLink="true">${url}</guid><pubDate>${pubDate}</pubDate><description>${escapeXml(`The Daily Tape market-close report for ${item.date}.`)}</description></item>`;
  }).join("");

  const xml = `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>The Daily Tape</title><link>${siteUrl}/</link><description>Automated U.S. market-close intelligence.</description><language>en-us</language>${xmlItems}</channel></rss>`;
  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
