import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import DailyTape, { type DailyReport } from "../../DailyTape";

export const dynamic = "force-static";
export const dynamicParams = false;

const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");

function reportsDir() {
  return path.join(process.cwd(), "public", "reports");
}

function reportPath(date: string) {
  return path.join(reportsDir(), date, "report.json");
}

function reportDates() {
  const dir = reportsDir();
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && datePattern.test(entry.name))
    .filter((entry) => fs.existsSync(reportPath(entry.name)))
    .map((entry) => entry.name)
    .sort();
}

function readReport(date: string): DailyReport | null {
  if (!datePattern.test(date)) return null;
  const file = reportPath(date);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf8")) as DailyReport;
}

type ArchiveComparison = {
  sampleSize: number;
  breadthAverage: number | null;
  breadthDelta: number | null;
  vixPercentile: number | null;
  regimeStreak: number;
  sp500FiveSessionReturn: number | null;
};

function average(values: number[]) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function buildArchiveComparison(date: string, report: DailyReport): ArchiveComparison {
  const dates = reportDates();
  const index = dates.indexOf(date);
  const priorDates = index > 0 ? dates.slice(Math.max(0, index - 20), index) : [];
  const priorReports = priorDates
    .map((item) => readReport(item))
    .filter((item): item is DailyReport => item !== null);

  const breadthValues = priorReports
    .map((item) => item.daily_market_breadth?.positive_sector_share)
    .filter(finite);
  const breadthAverage = average(breadthValues);
  const currentBreadth = report.daily_market_breadth?.positive_sector_share;
  const breadthDelta = finite(currentBreadth) && breadthAverage != null
    ? currentBreadth - breadthAverage
    : null;

  const currentVix = report.market_data?.["^VIX"]?.end_price;
  const vixSample = [...priorReports, report]
    .map((item) => item.market_data?.["^VIX"]?.end_price)
    .filter(finite);
  const vixPercentile = finite(currentVix) && vixSample.length
    ? (vixSample.filter((value) => value <= currentVix).length / vixSample.length) * 100
    : null;

  const currentRegime = report.derived_metrics?.risk_confirmation?.signal;
  let regimeStreak = currentRegime ? 1 : 0;
  if (currentRegime) {
    for (let cursor = priorReports.length - 1; cursor >= 0; cursor -= 1) {
      if (priorReports[cursor].derived_metrics?.risk_confirmation?.signal !== currentRegime) break;
      regimeStreak += 1;
    }
  }

  const fiveReports = [...priorReports, report].slice(-5);
  const fiveReturns = fiveReports
    .map((item) => item.market_data?.["^GSPC"]?.pct_change)
    .filter(finite);
  const sp500FiveSessionReturn = fiveReturns.length === fiveReports.length && fiveReturns.length
    ? (fiveReturns.reduce((factor, value) => factor * (1 + value / 100), 1) - 1) * 100
    : null;

  return {
    sampleSize: priorReports.length,
    breadthAverage,
    breadthDelta,
    vixPercentile,
    regimeStreak,
    sp500FiveSessionReturn,
  };
}

export function generateStaticParams() {
  return reportDates().map((date) => ({ date }));
}

export async function generateMetadata({ params }: { params: Promise<{ date: string }> }): Promise<Metadata> {
  const { date } = await params;
  const report = readReport(date);
  if (!report) return {};

  const displayDate = new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T12:00:00Z`));
  const title = `Stock Market Summary – ${displayDate} | The Daily Tape`;
  const description = `The Daily Tape market-close report for ${displayDate}, covering major indexes, sector breadth, leadership, rates, commodities, global markets, and crypto.`;
  const url = `${siteUrl}/reports/${date}/`;

  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      title,
      description,
      url,
      siteName: "The Daily Tape",
      type: "article",
      images: [`${siteUrl}/og.png`],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [`${siteUrl}/og.png`],
    },
  };
}

export default async function ArchivedReportPage({ params }: { params: Promise<{ date: string }> }) {
  const { date } = await params;
  const report = readReport(date);
  if (!report) notFound();

  const dates = reportDates();
  const index = dates.indexOf(date);
  const previousDate = index > 0 ? dates[index - 1] : null;
  const nextDate = index >= 0 && index < dates.length - 1 ? dates[index + 1] : null;
  const archiveComparison = buildArchiveComparison(date, report);

  return (
    <DailyTape
      report={report}
      archived
      archiveHref="../"
      assetBaseHref="../../assets/"
      previousReportHref={previousDate ? `../${previousDate}/` : undefined}
      nextReportHref={nextDate ? `../${nextDate}/` : undefined}
      archiveComparison={archiveComparison}
    />
  );
}
