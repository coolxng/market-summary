import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import ArchiveClient, { type ArchiveReport } from "./ArchiveClient";

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

type StoredReport = {
  session_date?: string;
  market_data?: Record<string, { pct_change?: number; end_price?: number }>;
  daily_market_breadth?: { positive_sector_share?: number };
  derived_metrics?: { risk_confirmation?: { signal?: string } };
  narrative?: { editorial?: { headline?: string }; daily_takeaway?: { what_moved?: string } };
};

function formatDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T12:00:00Z`));
}

function finiteOrNull(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getReports(): ArchiveReport[] {
  const reportsDir = path.join(process.cwd(), "public", "reports");
  if (!fs.existsSync(reportsDir)) return [];

  return fs
    .readdirSync(reportsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && datePattern.test(entry.name))
    .map((entry) => {
      const file = path.join(reportsDir, entry.name, "report.json");
      if (!fs.existsSync(file)) return null;

      try {
        const report = JSON.parse(fs.readFileSync(file, "utf8")) as StoredReport;
        const headline =
          report.narrative?.editorial?.headline ??
          report.narrative?.daily_takeaway?.what_moved ??
          "Completed U.S. market session";

        return {
          date: entry.name,
          displayDate: formatDate(entry.name),
          headline,
          sp500: finiteOrNull(report.market_data?.["^GSPC"]?.pct_change),
          nasdaq: finiteOrNull(report.market_data?.["^IXIC"]?.pct_change),
          vix: finiteOrNull(report.market_data?.["^VIX"]?.end_price),
          breadth: finiteOrNull(report.daily_market_breadth?.positive_sector_share),
          regime: report.derived_metrics?.risk_confirmation?.signal ?? "mixed",
        };
      } catch {
        return null;
      }
    })
    .filter((report): report is ArchiveReport => report !== null)
    .sort((a, b) => b.date.localeCompare(a.date));
}

export default function ReportsPage() {
  return <ArchiveClient reports={getReports()} />;
}
