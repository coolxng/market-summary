import type { Metadata } from "next";
import { notFound } from "next/navigation";
import DailyTape, { type ArchiveComparison, type DailyReport } from "../../DailyTape";
import { buildRegimeTimeline, classifyRegime } from "../../lib/regime";
import { archivedDates, archivedReport } from "../../lib/archive";

export const dynamic = "force-static";
export const dynamicParams = false;

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");
const reportDates = archivedDates;
const readReport = archivedReport;

function topSectorOf(report: DailyReport) {
  return Object.entries(report.daily_sector_performance ?? {}).filter(([, value]) => finite(value)).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
}

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

  const currentRegime = classifyRegime(report).regime;
  let regimeStreak = currentRegime === "unavailable" ? 0 : 1;
  if (regimeStreak) {
    for (let cursor = priorReports.length - 1; cursor >= 0; cursor -= 1) {
      if (classifyRegime(priorReports[cursor]).regime !== currentRegime) break;
      regimeStreak += 1;
    }
  }

  const fiveReports = [...priorReports, report].slice(-5);
  const fiveReturns = fiveReports
    .map((item) => item.market_data?.["^GSPC"]?.pct_change)
    .filter(finite);
  // Only reported once five consecutive archived sessions exist; a shorter
  // sample is not relabeled as a five-session return.
  const sp500FiveSessionReturn = fiveReports.length === 5 && fiveReturns.length === 5
    ? (fiveReturns.reduce((factor, value) => factor * (1 + value / 100), 1) - 1) * 100
    : null;

  const topSector = topSectorOf(report);
  let topSectorStreak = topSector ? 1 : 0;
  if (topSector) {
    for (let cursor = priorReports.length - 1; cursor >= 0; cursor -= 1) {
      if (topSectorOf(priorReports[cursor]) !== topSector) break;
      topSectorStreak += 1;
    }
  }
  const leadWindow = [...priorReports, report].slice(-10);
  const topSectorLedCount = topSector ? leadWindow.filter((item) => topSectorOf(item) === topSector).length : 0;

  return {
    sampleSize: priorReports.length,
    topSector: topSector ? topSector.replace(/\s*\([A-Z]+\)$/, "") : null,
    topSectorStreak,
    topSectorLedCount,
    topSectorWindow: leadWindow.length,
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
      regimeTimeline={buildRegimeTimeline(report, dates.map((item) => ({ report: readReport(item), href: `${item}/` })).filter((entry): entry is { report: DailyReport; href: string } => entry.report !== null))}
      regimeHrefBase="../"
    />
  );
}
