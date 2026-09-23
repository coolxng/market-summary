"use client";

import { useEffect, useMemo, useState } from "react";
import AssetLogo from "../components/AssetLogo";
import { sparkPoints } from "../lib/chart";
import { readWatchlist, subscribeWatchlist } from "../lib/watchlist";
import type { AssetSummary } from "../lib/assetSummary";
import styles from "./assets.module.css";

type SortKey = "price" | "change";
type Sort = { key: SortKey; dir: "desc" | "asc" } | null;
export type AssetGroup = { id: string; title: string; changeLabel: string; rows: AssetSummary[] };

function AssetRow({ asset, showLogo }: { asset: AssetSummary; showLogo: boolean }) {
  const spark = sparkPoints(asset.spark);
  return (
    <li>
      <a href={`./${asset.slug}/`}>
        <span className={styles.name}>
          {showLogo && <AssetLogo src={asset.logo} symbol={asset.symbol} size={26} />}
          <span className={styles.nameText}><strong>{asset.name}</strong><small>{asset.symbol}</small></span>
        </span>
        <span className={`${styles.spark} ${asset.sparkTone}`} aria-hidden="true">
          {spark && <svg viewBox="0 0 100 32" preserveAspectRatio="none"><polyline points={spark} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" /></svg>}
        </span>
        <span className={styles.price}>{asset.priceText}</span>
        <span className={`${styles.change} ${asset.tone}`}>{asset.changeText}</span>
      </a>
    </li>
  );
}

function sortRows(rows: AssetSummary[], sort: Sort) {
  if (!sort) return rows;
  const value = (row: AssetSummary) => (sort.key === "price" ? row.price : row.change);
  // Rows without a value always sink to the bottom, whichever direction.
  return [...rows].sort((a, b) => {
    const x = value(a);
    const y = value(b);
    if (x == null || y == null) return x == null ? (y == null ? 0 : 1) : -1;
    return sort.dir === "desc" ? y - x : x - y;
  });
}

function SortHeader({ label, column, sort, onSort }: { label: string; column: SortKey; sort: Sort; onSort: (key: SortKey) => void }) {
  const active = sort?.key === column;
  return (
    <button type="button" className={styles.sortButton} onClick={() => onSort(column)} aria-pressed={active}
      aria-label={`Sort by ${label}${active ? (sort!.dir === "desc" ? ", highest first" : ", lowest first") : ""}`}>
      {label}<i aria-hidden="true">{active ? (sort!.dir === "desc" ? "↓" : "↑") : "↕"}</i>
    </button>
  );
}

function Group({ group, showLogos }: { group: AssetGroup; showLogos: boolean }) {
  const [sort, setSort] = useState<Sort>(null);
  // Highest first, then lowest first, then back to the catalog order.
  const onSort = (key: SortKey) => setSort((current) => (current?.key !== key ? { key, dir: "desc" } : current.dir === "desc" ? { key, dir: "asc" } : null));
  const rows = useMemo(() => sortRows(group.rows, sort), [group.rows, sort]);
  return (
    <section id={group.id} className={styles.group} aria-labelledby={`${group.id}-title`}>
      <div className={styles.groupHead}>
        <h2 id={`${group.id}-title`}>{group.title}</h2>
        <span className={styles.columnLabel} aria-hidden="true">1M</span>
        <SortHeader label="Last" column="price" sort={sort} onSort={onSort} />
        <SortHeader label={group.changeLabel} column="change" sort={sort} onSort={onSort} />
      </div>
      <ul className={styles.rows}>
        {rows.map((asset) => <AssetRow key={asset.slug} asset={asset} showLogo={showLogos} />)}
      </ul>
    </section>
  );
}

export default function AssetsBrowser({ groups, all }: { groups: AssetGroup[]; all: AssetSummary[] }) {
  const [watchlist, setWatchlist] = useState<string[]>([]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setWatchlist(readWatchlist()));
    const unsubscribe = subscribeWatchlist(setWatchlist);
    return () => {
      window.cancelAnimationFrame(frame);
      unsubscribe();
    };
  }, []);

  const watched = watchlist.map((slug) => all.find((asset) => asset.slug === slug)).filter((asset): asset is AssetSummary => Boolean(asset));

  return (
    <>
      {watched.length > 0 && (
        <Group group={{ id: "watchlist", title: "Your watchlist", changeLabel: "1D", rows: watched }} showLogos />
      )}
      {groups.map((group) => <Group key={group.id} group={group} showLogos={group.id === "equity"} />)}
    </>
  );
}
