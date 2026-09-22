"use client";

import { useEffect, useState } from "react";
import styles from "./reports.module.css";

const logoSrc = "https://coolxng.github.io/market-summary/logo.png";

export type ArchiveReport = {
  date: string;
  displayDate: string;
  headline: string;
  sp500: number | null;
  nasdaq: number | null;
  vix: number | null;
  breadth: number | null;
  regime: string;
};

function formatPct(value: number | null) {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export default function ArchiveClient({ reports }: { reports: ArchiveReport[] }) {
  const [theme, setTheme] = useState<"paper" | "ink">("paper");

  useEffect(() => {
    const saved = window.localStorage.getItem("daily-tape-theme");
    if (saved !== "ink") return;
    const frame = window.requestAnimationFrame(() => setTheme("ink"));
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

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="../" aria-label="The Daily Tape home">
          <span className="brand-mark" style={{ backgroundImage: `url("${logoSrc}")` }} />
          <span>THE DAILY TAPE</span>
        </a>
        <nav aria-label="Archive navigation">
          <a href="../">Current report</a>
          <a href="../morning/">Morning</a>
          <a href="./" aria-current="page">Archive</a>
          <a href="../search/">Search</a>
        </nav>
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "paper" ? "dark" : "light"} theme`}
        >
          <span>{theme === "paper" ? "◐" : "◑"}</span>{theme === "paper" ? "Ink" : "Paper"}
        </button>
      </header>

      <div className={styles.page}>
        <section className={styles.hero}>
          <div className={styles.issueLine}>
            <span>HISTORICAL MARKET INTELLIGENCE</span>
            <span><b>ARCHIVED</b> {reports.length} SESSION{reports.length === 1 ? "" : "S"}</span>
            <span><b>FORMAT</b> DAILY TAPE</span>
          </div>

          <div className={styles.heroGrid}>
            <div>
              <p className={styles.kicker}>THE ARCHIVE</p>
              <h1>Past sessions.</h1>
            </div>
            <p className={styles.dek}>
              Every completed report keeps the same data-first Daily Tape experience, with its original session data, commentary, breadth, leadership, macro context, and price paths.
            </p>
          </div>
        </section>

        {reports.length > 0 && (
          <section className={styles.regimeSection}>
            <div className={styles.sectionHeading}>
              <div><p className={styles.kicker}>REGIME HISTORY</p><h2>How the tape changed</h2></div>
              <p>Each marker uses the archived report’s rules-based risk confirmation signal. It is a historical classification, not a forecast.</p>
            </div>
            <div className={styles.regimeTimeline} aria-label="Archived market regime history">
              {reports.slice(0, 30).reverse().map((report) => (
                <a
                  href={`./${report.date}/`}
                  className={styles[`regime_${report.regime}`] ?? styles.regime_mixed}
                  title={`${report.displayDate}: ${report.regime.replaceAll("_", " ")}`}
                  key={report.date}
                >
                  <span>{report.date.slice(5)}</span>
                </a>
              ))}
            </div>
            <div className={styles.regimeLegend}>
              <span><i className={styles.regime_risk_on_confirmed} />Constructive</span>
              <span><i className={styles.regime_mixed} />Mixed</span>
              <span><i className={styles.regime_risk_off_confirmed} />Defensive</span>
            </div>
          </section>
        )}

        <section className={styles.listSection}>
          <div className={styles.sectionHeading}>
            <div>
              <p className={styles.kicker}>SESSION HISTORY</p>
              <h2>Browse the tape</h2>
            </div>
            <p>Newest first. Each issue is a permanent snapshot of that completed U.S. trading session.</p>
          </div>

          {reports.length === 0 ? (
            <p className={styles.empty}>No archived sessions yet.</p>
          ) : (
            <div className={styles.reportList}>
              {reports.map((report, index) => (
                <a className={styles.reportRow} href={`./${report.date}/`} key={report.date}>
                  <span className={styles.issueNumber}>{String(reports.length - index).padStart(3, "0")}</span>
                  <div className={styles.reportIdentity}>
                    <strong>{report.displayDate}</strong>
                    <span>{report.headline}</span>
                  </div>
                  <div className={styles.stat}>
                    <span>S&amp;P 500</span>
                    <strong className={report.sp500 != null && report.sp500 >= 0 ? styles.up : styles.down}>{formatPct(report.sp500)}</strong>
                  </div>
                  <div className={styles.stat}>
                    <span>NASDAQ</span>
                    <strong className={report.nasdaq != null && report.nasdaq >= 0 ? styles.up : styles.down}>{formatPct(report.nasdaq)}</strong>
                  </div>
                  <div className={styles.stat}>
                    <span>VIX</span>
                    <strong>{report.vix == null ? "—" : report.vix.toFixed(2)}</strong>
                  </div>
                  <div className={styles.stat}>
                    <span>POSITIVE SECTORS</span>
                    <strong>{report.breadth == null ? "—" : `${report.breadth.toFixed(1)}%`}</strong>
                  </div>
                  <b className={styles.open}>Open →</b>
                </a>
              ))}
            </div>
          )}
        </section>

        <footer className={styles.footer}>
          <div><strong>THE DAILY TAPE</strong><span>Signal over noise.</span></div>
          <div><span>{reports.length} ARCHIVED SESSION{reports.length === 1 ? "" : "S"}</span><span>PERMANENT DAILY SNAPSHOTS</span></div>
        </footer>
      </div>
    </main>
  );
}
