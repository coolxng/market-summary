"use client";

import { useEffect, useMemo, useState } from "react";
import { readWatchlist, subscribeWatchlist, WATCHLIST_MAX, writeWatchlist } from "../lib/watchlist";

export type WatchAsset = {
  slug: string;
  symbol: string;
  name: string;
  category: string;
  price: number | null;
  /** One-day change for the report session only: percent, or percentage points for yields. */
  change: number | null;
  changeUnit: "pct" | "bps";
  pricePrefix?: string;
  priceSuffix?: string;
  digits?: number;
  /** Up to one month of daily closes for the sparkline. */
  spark: number[];
  /** Verified catalysts in this issue whose source tagged the asset. */
  catalysts: number;
  /** Set when the row's own session differs from the report session. */
  otherSession?: string | null;
  /** True for overseas and 24/7 markets, whose own calendar legitimately differs. */
  localCalendar?: boolean;
};

function formatPrice(asset: WatchAsset) {
  if (asset.price == null || !Number.isFinite(asset.price)) return "—";
  const digits = asset.digits ?? (Math.abs(asset.price) >= 10000 ? 0 : 2);
  const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(asset.price);
  return `${asset.pricePrefix ?? ""}${number}${asset.priceSuffix ?? ""}`;
}

function formatChange(asset: WatchAsset) {
  if (asset.change == null || !Number.isFinite(asset.change)) return "—";
  if (asset.changeUnit === "bps") {
    const bps = Math.round(asset.change * 100);
    return `${bps >= 0 ? "+" : ""}${bps} bps`;
  }
  return `${asset.change >= 0 ? "+" : ""}${asset.change.toFixed(2)}%`;
}

function Spark({ values, name }: { values: number[]; name: string }) {
  if (values.length < 2) return <span className="watchlist-card__nospark">No 1M history stored</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 100},${30 - ((value - min) / span) * 26}`).join(" ");
  const up = values.at(-1)! >= values[0];
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" role="img" aria-label={`${name}, one month of daily closes, ${up ? "higher" : "lower"} than a month earlier`}>
      <polyline points={points} fill="none" stroke={up ? "var(--up)" : "var(--down)"} strokeWidth="1.8" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export default function WatchlistPanel({ assets, assetBaseHref, sessionLabel }: { assets: WatchAsset[]; assetBaseHref: string; sessionLabel: string }) {
  const [watchlist, setWatchlist] = useState<string[] | null>(null);
  const [selection, setSelection] = useState("");

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setWatchlist(readWatchlist()));
    const unsubscribe = subscribeWatchlist(setWatchlist);
    return () => {
      window.cancelAnimationFrame(frame);
      unsubscribe();
    };
  }, []);

  const list = useMemo(() => watchlist ?? [], [watchlist]);
  const full = list.length >= WATCHLIST_MAX;
  const bySlug = useMemo(() => Object.fromEntries(assets.map((asset) => [asset.slug, asset])), [assets]);
  const groups = useMemo(() => {
    const result = new Map<string, WatchAsset[]>();
    for (const asset of assets) {
      if (list.includes(asset.slug)) continue;
      result.set(asset.category, [...(result.get(asset.category) ?? []), asset]);
    }
    return [...result.entries()];
  }, [assets, list]);
  const watched = list.map((slug) => bySlug[slug]).filter((asset): asset is WatchAsset => Boolean(asset));

  const add = () => {
    if (!selection || full) return;
    setWatchlist(writeWatchlist([...readWatchlist(), selection]));
    setSelection("");
  };
  const remove = (slug: string) => setWatchlist(writeWatchlist(readWatchlist().filter((item) => item !== slug)));

  return (
    <section className="watchlist-panel report-subsection report-utility" id="watchlist" aria-labelledby="watchlist-title">
      <div className="section-heading">
        <div>
          <p className="section-kicker"><span className="section-kicker__chapter">Overview</span><span>Your tape · Personal</span></p>
          <h3 id="watchlist-title">Your watchlist</h3>
        </div>
        <div className="section-heading__aside"><p>Pin up to {WATCHLIST_MAX} tracked markets on this device. Stored only in this browser; nothing is sent anywhere, and the published report is unchanged.</p></div>
      </div>

      <div className="watchlist-controls">
        <label className="visually-hidden" htmlFor="watchlist-select">Choose an asset to watch</label>
        <select id="watchlist-select" value={selection} onChange={(event) => setSelection(event.target.value)} disabled={watchlist === null || full}>
          <option value="">{full ? "Watchlist is full" : "Add a tracked asset…"}</option>
          {groups.map(([category, items]) => (
            <optgroup key={category} label={category}>
              {items.map((asset) => <option value={asset.slug} key={asset.slug}>{asset.symbol} · {asset.name}</option>)}
            </optgroup>
          ))}
        </select>
        <button type="button" onClick={add} disabled={!selection || full}>Add to watchlist</button>
        <span className="watchlist-count" aria-live="polite">{list.length} / {WATCHLIST_MAX}</span>
      </div>

      {watched.length ? (
        <ul className="watchlist-grid">
          {watched.map((asset) => (
            <li className="watchlist-card" key={asset.slug}>
              <div className="watchlist-card__head">
                <span>{asset.symbol}</span>
                <button type="button" onClick={() => remove(asset.slug)} aria-label={`Remove ${asset.name} from watchlist`}>×</button>
              </div>
              <strong>{formatPrice(asset)}</strong>
              <p>{asset.name}{asset.otherSession && <small className={asset.localCalendar ? "local-session" : "local-session local-session--warn"}>{asset.localCalendar ? "Local session" : "Session"} {asset.otherSession}</small>}</p>
              <div className="watchlist-card__spark"><Spark values={asset.spark} name={asset.name} /></div>
              <div className="watchlist-card__foot">
                <b className={asset.change == null || asset.change === 0 ? "" : asset.change > 0 ? "positive" : "negative"}>{formatChange(asset)} <small>1D</small></b>
                {asset.catalysts > 0 && <a className="watchlist-card__catalyst" href={`${assetBaseHref}${asset.slug}/#asset-catalysts`}>{asset.catalysts} tagged</a>}
                <a href={`${assetBaseHref}${asset.slug}/`}>Open →</a>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="watchlist-empty">
          <strong>{watchlist === null ? "Loading your watchlist…" : "Build your daily check."}</strong>
          <p>Add the indexes, sectors, stocks, rates, commodities or crypto you follow. Prices and moves come from the {sessionLabel} Close Tape.</p>
        </div>
      )}
    </section>
  );
}
