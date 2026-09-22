"use client";

import { useEffect, useMemo, useState } from "react";

export type WatchAsset = {
  slug: string;
  symbol: string;
  name: string;
  price: number | null;
  pct_change: number | null;
};

function formatPrice(value: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 10000) return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(value);
}

function formatPct(value: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export default function WatchlistPanel({
  assets,
  assetBaseHref,
}: {
  assets: WatchAsset[];
  assetBaseHref: string;
}) {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [selection, setSelection] = useState("");

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        const stored = JSON.parse(window.localStorage.getItem("daily-tape-watchlist") || "[]");
        if (Array.isArray(stored)) setWatchlist(stored.filter((value) => typeof value === "string"));
      } catch {
        setWatchlist([]);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const available = useMemo(
    () => assets.filter((asset) => !watchlist.includes(asset.slug)),
    [assets, watchlist],
  );
  const watched = watchlist
    .map((slug) => assets.find((asset) => asset.slug === slug))
    .filter((asset): asset is WatchAsset => Boolean(asset));

  const save = (next: string[]) => {
    setWatchlist(next);
    window.localStorage.setItem("daily-tape-watchlist", JSON.stringify(next));
  };

  const add = () => {
    if (!selection || watchlist.includes(selection)) return;
    save([...watchlist, selection]);
    setSelection("");
  };

  return (
    <section className="watchlist-panel section-block" id="watchlist">
      <div className="section-heading">
        <div><p className="section-kicker">PERSONAL TAPE</p><h2>Your watchlist</h2></div>
        <p>Pin tracked markets locally on this device. No account, login, or server-side profile is required.</p>
      </div>

      <div className="watchlist-controls">
        <select value={selection} onChange={(event) => setSelection(event.target.value)} aria-label="Choose an asset to watch">
          <option value="">Add a tracked asset…</option>
          {available.map((asset) => <option value={asset.slug} key={asset.slug}>{asset.symbol} · {asset.name}</option>)}
        </select>
        <button onClick={add} disabled={!selection}>Add to watchlist</button>
      </div>

      {watched.length ? (
        <div className="watchlist-grid">
          {watched.map((asset) => (
            <article className="watchlist-card" key={asset.slug}>
              <div>
                <span>{asset.symbol}</span>
                <button onClick={() => save(watchlist.filter((slug) => slug !== asset.slug))} aria-label={`Remove ${asset.name} from watchlist`}>×</button>
              </div>
              <strong>{formatPrice(asset.price)}</strong>
              <p>{asset.name}</p>
              <div className="watchlist-card__foot">
                <b className={(asset.pct_change ?? 0) >= 0 ? "positive" : "negative"}>{formatPct(asset.pct_change)}</b>
                <a href={`${assetBaseHref}${asset.slug}/`}>Open →</a>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="watchlist-empty">
          <strong>Build your daily check.</strong>
          <p>Add the indexes, sectors, stocks, rates, commodities, or crypto you actually follow. Your picks stay in this browser.</p>
        </div>
      )}
    </section>
  );
}
