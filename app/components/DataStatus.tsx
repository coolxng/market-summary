import type { DataQuality, FeedStatus } from "../lib/report";
import { formatSessionDate } from "../lib/format";

const SOURCE_NAMES: Record<string, string> = {
  yahoo_finance: "Yahoo Finance",
  stooq: "Stooq (fallback)",
};

export function dataStatusLabel(quality: DataQuality | undefined) {
  if (!quality) return { label: "Not recorded", tone: "muted" as const };
  const overall = quality.overall ?? (quality.status === "healthy" ? "verified" : quality.status === "degraded" ? "partial" : "limited");
  if (overall === "verified") return { label: "Verified", tone: "good" as const };
  if (overall === "limited") return { label: "Limited", tone: "bad" as const };
  if (quality.unavailable_feeds?.length) return { label: "Some feeds unavailable", tone: "warn" as const };
  return { label: "Partial", tone: "warn" as const };
}

export function marketSources(quality: DataQuality | undefined) {
  const keys = Object.keys(quality?.sources ?? { yahoo_finance: 1 });
  return keys.map((key) => SOURCE_NAMES[key] ?? key).join(" · ");
}

/** Compact trust strip shown under the masthead. */
export default function DataStatus({ sessionDate, quality }: { sessionDate: string; quality: DataQuality | undefined }) {
  const status = dataStatusLabel(quality);
  return (
    <dl className="data-status" aria-label="Data freshness and status">
      <div><dt>Data freshness</dt><dd>Through {formatSessionDate(sessionDate, { month: "short", day: "numeric", year: "numeric" })} close</dd></div>
      <div><dt>Data status</dt><dd className={`data-status__value data-status__value--${status.tone}`}>{status.label}{quality ? ` · ${quality.valid}/${quality.total} quotes` : ""}</dd></div>
      <div><dt>Market data</dt><dd>{marketSources(quality)}</dd></div>
      <div><dd><a href="#data-health">Source detail ↓</a></dd></div>
    </dl>
  );
}

const FEED_LABEL: Record<FeedStatus["status"], string> = {
  ok: "Available",
  empty: "Checked · no items",
  unavailable: "Unavailable",
  disabled: "Disabled",
};

export function FeedHealthList({ feeds }: { feeds: FeedStatus[] }) {
  if (!feeds.length) return null;
  return (
    <ul className="feed-health">
      {feeds.map((feed) => (
        <li key={feed.id}>
          <i className={`feed-health__dot feed-health__dot--${feed.status}`} aria-hidden="true" />
          {feed.source_url ? <a href={feed.source_url} target="_blank" rel="noopener noreferrer" data-outbound="source">{feed.name}</a> : <span>{feed.name}</span>}
          <b>{FEED_LABEL[feed.status]}</b>
        </li>
      ))}
    </ul>
  );
}
