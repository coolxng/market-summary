import type { DataQuality, FeedStatus } from "../lib/report";
import { formatSessionDate, safeHref } from "../lib/format";

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

/**
 * One-line trust indicator under the issue line. Quiet when every quote
 * verified; louder as coverage degrades, and a boxed alert when limited.
 */
export default function DataStatus({ sessionDate, quality }: { sessionDate: string; quality: DataQuality | undefined }) {
  const status = dataStatusLabel(quality);
  const through = formatSessionDate(sessionDate, { month: "short", day: "numeric" });
  const counts = quality ? `${quality.valid}/${quality.total} quotes verified` : null;
  return (
    <p className={`data-status data-status--${status.tone}`} role={status.tone === "bad" ? "alert" : undefined}>
      <i className="data-status__dot" aria-hidden="true" />
      {status.tone === "muted"
        ? <span className="data-status__label">Data status not recorded</span>
        : <>
            {counts && <span className="data-status__count">{counts}</span>}
            {status.tone !== "good" && <span className="data-status__label">{status.label}</span>}
          </>}
      <span className="data-status__meta">Through {through} close · {marketSources(quality)}</span>
      <a href="#data-health">Source details ↓</a>
    </p>
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
          {feed.source_url ? <a href={safeHref(feed.source_url)} target="_blank" rel="noopener noreferrer" data-outbound="source">{feed.name}</a> : <span>{feed.name}</span>}
          <b>{FEED_LABEL[feed.status]}</b>
        </li>
      ))}
    </ul>
  );
}
