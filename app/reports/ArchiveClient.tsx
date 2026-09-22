"use client";

import { useDeferredValue, useMemo, useState } from "react";
import SiteHeader from "../components/SiteHeader";
import RegimeStrip from "../components/RegimeStrip";
import KeyboardShortcuts from "../components/KeyboardShortcuts";
import { REGIME_LABEL, type RegimeEntry, type RegimeKey } from "../lib/regime";
import styles from "./reports.module.css";

export type ArchiveReport = {
  date: string;
  displayDate: string;
  weekday: string;
  month: string;
  headline: string;
  sp500: number | null;
  nasdaq: number | null;
  vix: number | null;
  breadth: number | null;
  regime: RegimeKey;
  regimeBasis: "published" | "derived" | "unavailable";
  topSector: string | null;
  bottomSector: string | null;
  leader: string | null;
  laggard: string | null;
  search: string;
};

function formatPct(value: number | null) {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function tone(value: number | null) {
  return value == null || value === 0 ? "" : value > 0 ? styles.up : styles.down;
}

function shortSector(name: string | null) {
  return name ? name.replace(/\s*\([A-Z]+\)$/, "") : "—";
}

const REGIME_FILTERS: Array<RegimeKey | "all"> = ["all", "constructive", "mixed", "defensive", "unavailable"];

export default function ArchiveClient({ reports, timeline, rule }: { reports: ArchiveReport[]; timeline: RegimeEntry[]; rule?: string }) {
  const [query, setQuery] = useState("");
  const [regime, setRegime] = useState<RegimeKey | "all">("all");
  const deferredQuery = useDeferredValue(query);

  const filtered = useMemo(() => {
    const terms = deferredQuery.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return reports.filter((report) =>
      (regime === "all" || report.regime === regime) && terms.every((term) => report.search.includes(term)),
    );
  }, [deferredQuery, regime, reports]);

  const months = useMemo(() => {
    const groups: Array<{ month: string; items: ArchiveReport[] }> = [];
    for (const report of filtered) {
      const last = groups.at(-1);
      if (last?.month === report.month) last.items.push(report);
      else groups.push({ month: report.month, items: [report] });
    }
    return groups;
  }, [filtered]);

  const issueNumber = (date: string) => String(reports.length - reports.findIndex((report) => report.date === date)).padStart(3, "0");

  return (
    <main id="main">
      <SiteHeader root="../" current="reports" />
      <KeyboardShortcuts bindings={{ "/": { kind: "focus", id: "archive-search" }, h: { kind: "href", href: "../" } }} />

      <div className={styles.page}>
        <section className={styles.hero}>
          <div className={styles.issueLine}>
            <span>HISTORICAL MARKET INTELLIGENCE</span>
            <span><b>ARCHIVED</b> {reports.length} SESSION{reports.length === 1 ? "" : "S"}</span>
            <span><b>LATEST</b> {reports[0]?.displayDate.toUpperCase() ?? "—"}</span>
          </div>

          <div className={styles.heroGrid}>
            <div>
              <p className={styles.kicker}>THE ARCHIVE</p>
              <h1>Past sessions.</h1>
            </div>
            <p className={styles.dek}>
              Every completed session keeps its original data, commentary, breadth, leadership and price paths. Nothing is revised after publication.
            </p>
          </div>
        </section>

        {timeline.length > 0 && (
          <section className={styles.regimeSection} aria-labelledby="regime-title">
            <div className={styles.sectionHeading}>
              <div><p className={styles.kicker}>REGIME HISTORY</p><h2 id="regime-title">How the tape has read</h2></div>
              <p>Rules-based historical classification, not a forecast. Select a day to see its inputs; published days open that issue.</p>
            </div>
            <RegimeStrip entries={timeline} hrefBase="./" rule={rule} />
          </section>
        )}

        <section className={styles.listSection} aria-labelledby="sessions-title">
          <div className={styles.sectionHeading}>
            <div><p className={styles.kicker}>SESSION HISTORY</p><h2 id="sessions-title">Browse the tape</h2></div>
            <p>Newest first. Search by date, headline, sector or ticker, or filter by regime. Press / to search.</p>
          </div>

          <div className={styles.filters} role="search">
            <label className={styles.searchField}>
              <span>Search</span>
              <input
                id="archive-search"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="2026-09, Technology, NVDA, constructive…"
                autoComplete="off"
              />
            </label>
            <label className={styles.selectField}>
              <span>Regime</span>
              <select value={regime} onChange={(event) => setRegime(event.target.value as RegimeKey | "all")}>
                {REGIME_FILTERS.map((option) => <option key={option} value={option}>{option === "all" ? "All regimes" : REGIME_LABEL[option]}</option>)}
              </select>
            </label>
            <p className={styles.resultCount} aria-live="polite">{filtered.length} of {reports.length} session{reports.length === 1 ? "" : "s"}</p>
          </div>

          {reports.length === 0 ? (
            <p className={styles.empty}>No archived sessions yet.</p>
          ) : filtered.length === 0 ? (
            <p className={styles.empty}>No archived session matches that search. Try a date such as 2026-09 or a ticker such as NVDA.</p>
          ) : months.map((group) => (
            <section key={group.month} className={styles.monthGroup} aria-label={group.month}>
              <h3>{group.month}<span>{group.items.length} session{group.items.length === 1 ? "" : "s"}</span></h3>
              <ol className={styles.reportList}>
                {group.items.map((report) => (
                  <li key={report.date}>
                    <a className={styles.reportRow} href={`./${report.date}/`}>
                      <span className={styles.issueNumber}>{issueNumber(report.date)}</span>
                      <div className={styles.reportIdentity}>
                        <strong>{report.weekday}, {report.displayDate}</strong>
                        <span>{report.headline}</span>
                        <small>
                          <i className={`${styles.regimeTag} ${styles[`regimeTag_${report.regime}`] ?? ""}`}>{REGIME_LABEL[report.regime]}{report.regimeBasis === "derived" ? "*" : ""}</i>
                          Led by {shortSector(report.topSector)} · lagged by {shortSector(report.bottomSector)}
                          {report.leader && <> · best {report.leader}{report.laggard && report.laggard !== report.leader ? `, weakest ${report.laggard}` : ""}</>}
                        </small>
                      </div>
                      <div className={styles.stat}><span>S&amp;P 500</span><strong className={tone(report.sp500)}>{formatPct(report.sp500)}</strong></div>
                      <div className={styles.stat}><span>NASDAQ</span><strong className={tone(report.nasdaq)}>{formatPct(report.nasdaq)}</strong></div>
                      <div className={styles.stat}><span>VIX</span><strong>{report.vix == null ? "—" : report.vix.toFixed(2)}</strong></div>
                      <div className={styles.stat}><span>SECTORS UP</span><strong>{report.breadth == null ? "—" : `${report.breadth.toFixed(0)}%`}</strong></div>
                      <b className={styles.open} aria-hidden="true">Open →</b>
                    </a>
                  </li>
                ))}
              </ol>
            </section>
          ))}
          {reports.some((report) => report.regimeBasis === "derived") && (
            <p className={styles.footnote}>* Issue predates stored regime signals; classified from that issue&apos;s own stored data with the same rule.</p>
          )}
        </section>

        <footer className={styles.footer}>
          <div><strong>THE DAILY TAPE</strong><span>Signal over noise.</span></div>
          <div><span>{reports.length} ARCHIVED SESSION{reports.length === 1 ? "" : "S"}</span><span>PERMANENT DAILY SNAPSHOTS</span><a href="../feed.xml">RSS FEED</a></div>
        </footer>
      </div>
    </main>
  );
}
