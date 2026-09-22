"use client";

import { useEffect, useMemo, useState } from "react";
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
  const [theme, setTheme] = useState<"paper" | "ink">("paper");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (window.localStorage.getItem("daily-tape-theme") === "ink") setTheme("ink");
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const toggleTheme = () => {
    const next = theme === "paper" ? "ink" : "paper";
    document.documentElement.dataset.theme = next;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", next === "ink" ? "#080808" : "#f3f0e7");
    const favicon = document.getElementById("site-favicon") as HTMLLinkElement | null;
    if (favicon) favicon.href = new URL(next === "ink" ? "favicon-dark.svg" : "favicon-light.svg", favicon.href).href;
    window.localStorage.setItem("daily-tape-theme", next);
    setTheme(next);
  };

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
    <main>
      <header className="site-header">
        <a className="brand" href="../" aria-label="The Daily Tape home">
          <span className="brand-mark" style={{ backgroundImage: 'url("https://coolxng.github.io/market-summary/logo.png")' }} />
          <span>THE DAILY TAPE</span>
        </a>
        <nav aria-label="Search navigation"><a href="../">Current report</a><a href="../morning/">Morning</a><a href="../reports/">Archive</a><a href="./">Search</a></nav>
        <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
          <span className="theme-toggle__icon" aria-hidden="true">{theme === "paper" ? "◐" : "◑"}</span>
          <span className="theme-toggle__label">{theme === "paper" ? "Ink" : "Paper"}</span>
        </button>
      </header>

      <div className={styles.page}>
        <section className={styles.hero}>
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
