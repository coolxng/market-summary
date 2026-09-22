"use client";

import SiteHeader from "../components/SiteHeader";
import Breadcrumbs from "../components/Breadcrumbs";
import { useMemo, useState } from "react";
import styles from "./search.module.css";

export type SearchAsset = { slug: string; symbol: string; name: string; category: string };
export type SearchReport = { date: string; displayDate: string; headline: string };

export default function SearchClient({
  assets,
  reports,
}: {
  assets: SearchAsset[];
  reports: SearchReport[];
}) {
  const [query, setQuery] = useState("");

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
          <Breadcrumbs items={[{ label: "Close Tape", href: "../" }, { label: "Search" }]} />
          <p>POWER SEARCH</p>
          <h1>Find the tape.</h1>
          <span>Search tracked assets, sectors, rates, commodities, crypto, and archived sessions without leaving the Daily Tape.</span>
          <div className={styles.searchBox}>
            <span>/</span>
            <input
              autoFocus
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
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
              {assetResults.map((asset) => (
                <a href={`../assets/${asset.slug}/`} key={asset.slug}>
                  <div><strong>{asset.symbol}</strong><span>{asset.category}</span></div>
                  <p>{asset.name}</p>
                  <b>Open →</b>
                </a>
              ))}
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
                  <b>Open →</b>
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
