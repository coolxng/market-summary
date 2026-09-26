"use client";

import SiteHeader from "../components/SiteHeader";
import Breadcrumbs from "../components/Breadcrumbs";
import { useMemo, useState, useSyncExternalStore } from "react";
import styles from "./search.module.css";
import AssetLogo from "../components/AssetLogo";
import { sparkPoints } from "../lib/chart";
import type { AssetSummary } from "../lib/assetSummary";

export type SearchAsset = AssetSummary;
export type SearchReport = { date: string; displayDate: string; headline: string };

function subscribeToLocation() {
  return () => {};
}

function readLocationQuery() {
  return new URLSearchParams(window.location.search).get("q") ?? "";
}

function readServerQuery() {
  return "";
}

export default function SearchClient({
  assets,
  reports,
}: {
  assets: SearchAsset[];
  reports: SearchReport[];
}) {
  const locationQuery = useSyncExternalStore(subscribeToLocation, readLocationQuery, readServerQuery);
  const [queryOverride, setQueryOverride] = useState<string | null>(null);
  const query = queryOverride ?? locationQuery;

  const normalized = query.trim().toLowerCase();
  const assetResults = useMemo(() => {
    if (!normalized) return assets.slice(0, 12);
    return assets.filter((asset) =>
      [asset.symbol, asset.name, asset.category].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [assets, normalized]);

  const reportResults = useMemo(() => {
    if (!normalized) return reports.slice(0, 8);
    return reports.filter((report) =>
      [report.date, report.displayDate, report.headline].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [normalized, reports]);

  return (
    <main id="main">
      <SiteHeader root="../" current="search" />

      <div className={styles.page}>
        <section className={styles.hero}>
          <Breadcrumbs items={[{ label: "Today", href: "../" }, { label: "Search" }]} />
          <p>POWER SEARCH</p>
          <h1>Search markets and sessions.</h1>
          <span>Search tracked assets, sectors, rates, commodities, crypto, and archived sessions without leaving the Daily Tape.</span>
          <div className={styles.searchBox}>
            <span>/</span>
            <input
              autoFocus
              type="search"
              value={query}
              onChange={(event) => setQueryOverride(event.target.value)}
              placeholder="Search NVDA, Technology, 2026-09-18…"
              aria-label="Search The Daily Tape"
            />
            <kbd>ESC</kbd>
          </div>
        </section>

        <section className={styles.results}>
          <div className={styles.column}>
            <div className={styles.heading}><span>TRACKED ASSETS</span><small>{assetResults.length} result{assetResults.length === 1 ? "" : "s"}</small></div>
            <div className={styles.list}>
              {assetResults.map((asset) => {
                const spark = sparkPoints(asset.spark);
                return (
                  <a className={styles.assetRow} href={`../assets/${asset.slug}/`} key={asset.slug}>
                    <AssetLogo src={asset.logo} symbol={asset.symbol} size={30} />
                    <div className={styles.assetName}><p>{asset.name}</p><span>{asset.symbol} · {asset.category}</span></div>
                    <span className={`${styles.assetSpark} ${asset.sparkTone}`} aria-hidden="true">
                      {spark && <svg viewBox="0 0 100 32" preserveAspectRatio="none"><polyline points={spark} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" /></svg>}
                    </span>
                    <span className={styles.assetQuote}><strong>{asset.priceText}</strong><b className={asset.tone}>{asset.changeText}</b></span>
                  </a>
                );
              })}
              {!assetResults.length && <p className={styles.empty}>No tracked asset matches that search.</p>}
            </div>
          </div>
          <div className={styles.column}>
            <div className={styles.heading}><span>REPORT ARCHIVE</span><small>{reportResults.length} result{reportResults.length === 1 ? "" : "s"}</small></div>
            <div className={styles.list}>
              {reportResults.map((report) => (
                <a href={`../reports/${report.date}/`} key={report.date}>
                  <div><strong>{report.date}</strong><span>Archived session</span></div>
                  <p><b>{report.displayDate}</b><br />{report.headline}</p>
                  <i className={styles.arrow} aria-hidden="true">→</i>
                </a>
              ))}
              {!reportResults.length && <p className={styles.empty}>No archived report matches that search.</p>}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
