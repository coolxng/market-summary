import type { CatalystSet } from "../lib/report";
import { assetBySymbol } from "../lib/assets";
import { formatCentralDateTime } from "../lib/format";

export default function CatalystList({
  catalysts,
  assetBaseHref,
  limit = 6,
}: {
  catalysts: CatalystSet | undefined;
  assetBaseHref: string;
  limit?: number;
}) {
  if (!catalysts) {
    return <p className="data-empty">Verified catalysts were not captured for this issue.</p>;
  }
  const unavailable = catalysts.feeds.filter((feed) => feed.status === "unavailable");
  const items = catalysts.items.slice(0, limit);

  return (
    <div className="catalyst-list">
      {items.length === 0 && (
        <p className="data-empty">
          {unavailable.length === catalysts.feeds.filter((feed) => feed.status !== "disabled").length && unavailable.length > 0
            ? "Catalyst sources were unavailable when this issue was generated, so no developments are shown."
            : "No qualifying development from an official source or allowlisted publisher was published in this window. Nothing is substituted."}
        </p>
      )}
      <ol>
        {items.map((item) => {
          const tracked = (item.related_tickers ?? []).map((symbol) => assetBySymbol[symbol]).filter(Boolean);
          return (
            <li key={item.url} className="catalyst-row">
              <div className="catalyst-row__meta">
                <span className={item.source_type === "official" ? "catalyst-badge catalyst-badge--official" : "catalyst-badge"}>
                  {item.source_type === "official" ? "Official source" : "Reported"}
                </span>
                <span>{item.category ?? "Market news"}</span>
                <time dateTime={item.published_at ? new Date(item.published_at * 1000).toISOString() : undefined}>
                  {item.published_at ? formatCentralDateTime(item.published_at) : "Time not provided"}
                </time>
              </div>
              <a className="catalyst-row__title" href={item.url} target="_blank" rel="noopener noreferrer" data-outbound="catalyst">
                {item.title}
              </a>
              <div className="catalyst-row__foot">
                <span>{item.publisher}</span>
                {tracked.length > 0 && (
                  <span>
                    Tagged by source:{" "}
                    {tracked.map((asset, index) => (
                      <span key={asset.slug}>{index > 0 && ", "}<a href={`${assetBaseHref}${asset.slug}/`}>{asset.symbol}</a></span>
                    ))}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {unavailable.length > 0 && items.length > 0 && (
        <p className="feed-warning" role="note">Unavailable at generation: {unavailable.map((feed) => feed.name).join(", ")}.</p>
      )}
    </div>
  );
}
