import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import styles from "./reports.module.css";

export const metadata: Metadata = {
  title: "Daily Market Report Archive | The Daily Tape",
  description:
    "Browse archived U.S. stock market close reports from The Daily Tape, including index performance, sector breadth, mega-cap leadership, rates, commodities, global markets, and crypto.",
  alternates: { canonical: "./reports/" },
  openGraph: {
    title: "Daily Market Report Archive | The Daily Tape",
    description: "Browse previous Daily Tape market-close reports.",
    url: "./reports/",
    type: "website",
  },
};

const datePattern = /^\d{4}-\d{2}-\d{2}$/;

function getReports() {
  const reportsDir = path.join(process.cwd(), "public", "reports");
  if (!fs.existsSync(reportsDir)) return [];

  return fs
    .readdirSync(reportsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && datePattern.test(entry.name))
    .filter((entry) => fs.existsSync(path.join(reportsDir, entry.name, "index.html")))
    .map((entry) => entry.name)
    .sort()
    .reverse();
}

function formatDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T12:00:00Z`));
}

export default function ReportsPage() {
  const reports = getReports();

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <a href="../" className={styles.brand}>THE DAILY TAPE</a>
        <a href="../" className={styles.back}>Current report</a>
      </header>

      <section className={styles.hero}>
        <p>DAILY MARKET INTELLIGENCE</p>
        <h1>Market report archive</h1>
        <span>
          Permanent snapshots of completed U.S. trading sessions. Each report preserves the market data and commentary published for that session.
        </span>
      </section>

      <section className={styles.list} aria-label="Archived Daily Tape reports">
        {reports.length === 0 ? (
          <p className={styles.empty}>No archived sessions yet.</p>
        ) : (
          reports.map((date, index) => (
            <a className={styles.row} href={`./${date}/`} key={date}>
              <span>{String(reports.length - index).padStart(3, "0")}</span>
              <strong>{formatDate(date)}</strong>
              <small>{date}</small>
              <b>Open report →</b>
            </a>
          ))
        )}
      </section>

      <footer className={styles.footer}>
        <span>THE DAILY TAPE</span>
        <span>{reports.length} archived session{reports.length === 1 ? "" : "s"}</span>
      </footer>
    </main>
  );
}
