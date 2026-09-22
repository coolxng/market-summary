import report from "../../report_snapshot.json";
import type { Metadata } from "next";
import ArchiveClient, { type ArchiveReport } from "./ArchiveClient";
import { archivedReports, reportHeadline } from "../lib/archive";
import { buildRegimeTimeline, classifyRegime, REGIME_LABEL } from "../lib/regime";
import { formatSessionDate } from "../lib/format";
import { verified, isFiniteNumber, type DailyReport } from "../lib/report";

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

function pct(issue: DailyReport, symbol: string) {
  return verified(issue.market_data?.[symbol])?.pct_change ?? null;
}

function summarize(date: string, issue: DailyReport): ArchiveReport {
  const sectors = Object.entries(issue.daily_sector_performance ?? {}).filter(([, value]) => isFiniteNumber(value)).sort((a, b) => b[1] - a[1]);
  const names = Object.entries(issue.mega_cap_data ?? {})
    .map(([ticker, entry]) => [ticker, verified(entry.result)?.pct_change] as const)
    .filter((entry): entry is readonly [string, number] => entry[1] != null)
    .sort((a, b) => b[1] - a[1]);
  const { regime, basis } = classifyRegime(issue);
  const headline = reportHeadline(issue);
  const topSector = sectors[0]?.[0] ?? null;
  const bottomSector = sectors.at(-1)?.[0] ?? null;
  const leader = names[0]?.[0] ?? null;
  const laggard = names.at(-1)?.[0] ?? null;
  const displayDate = formatSessionDate(date);
  return {
    date,
    displayDate,
    weekday: formatSessionDate(date, { weekday: "short" }),
    month: formatSessionDate(date, { month: "long", year: "numeric" }),
    headline,
    sp500: pct(issue, "^GSPC"),
    nasdaq: pct(issue, "^IXIC"),
    vix: verified(issue.market_data?.["^VIX"])?.end_price ?? null,
    breadth: isFiniteNumber(issue.daily_market_breadth?.positive_sector_share) && sectors.length ? issue.daily_market_breadth.positive_sector_share : null,
    regime,
    regimeBasis: basis,
    topSector,
    bottomSector,
    leader,
    laggard,
    search: [
      date, displayDate, headline, REGIME_LABEL[regime], topSector, bottomSector,
      ...Object.keys(issue.mega_cap_data ?? {}), ...sectors.map(([name]) => name),
    ].filter(Boolean).join(" ").toLowerCase(),
  };
}

export default function ReportsPage() {
  const archive = archivedReports();
  const reports = archive.map(({ date, report: issue }) => summarize(date, issue)).reverse();
  const timeline = buildRegimeTimeline(report as unknown as DailyReport, archive.map(({ date, report: issue }) => ({ report: issue, href: `${date}/` })));
  return <ArchiveClient reports={reports} timeline={timeline} rule={(report as unknown as DailyReport).regime_history?.rule} />;
}
