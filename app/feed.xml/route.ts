import { archivedReports, reportHeadline } from "../lib/archive";
import { decodeText } from "../lib/format";

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
  const items = archivedReports().map(({ date, report }) => ({
    date,
    headline: reportHeadline(report),
    summary: decodeText(report.narrative?.editorial?.opening_summary ?? report.narrative?.daily_takeaway?.what_moved ?? `The Daily Tape market-close report for ${date}.`),
  }));

  items.sort((a, b) => b.date.localeCompare(a.date));
  const xmlItems = items.slice(0, 30).map((item) => {
    const url = `${siteUrl}/reports/${item.date}/`;
    const pubDate = new Date(`${item.date}T21:00:00Z`).toUTCString();
    return `<item><title>${escapeXml(item.headline)}</title><link>${url}</link><guid isPermaLink="true">${url}</guid><pubDate>${pubDate}</pubDate><description>${escapeXml(item.summary)}</description></item>`;
  }).join("");

  const lastBuildDate = items[0] ? new Date(`${items[0].date}T21:00:00Z`).toUTCString() : new Date(0).toUTCString();
  // The stylesheet only affects browsers opening the feed directly (they render a
  // readable page instead of raw XML); feed readers ignore it.
  const xml = `<?xml version="1.0" encoding="UTF-8"?><?xml-stylesheet type="text/xsl" href="feed.xsl"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>The Daily Tape</title><link>${siteUrl}/</link><atom:link href="${siteUrl}/feed.xml" rel="self" type="application/rss+xml"/><description>Automated U.S. market-close intelligence.</description><language>en-us</language><lastBuildDate>${lastBuildDate}</lastBuildDate>${xmlItems}</channel></rss>`;
  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
