import { archivedReports, reportHeadline } from "../lib/archive";

export const dynamic = "force-static";

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");

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
  const items = archivedReports().map(({ date, report }) => ({ date, headline: reportHeadline(report) }));

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
