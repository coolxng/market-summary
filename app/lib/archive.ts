import fs from "node:fs";
import path from "node:path";
import type { DailyReport } from "./report";
import { decodeText } from "./format";

// Build-time access to archived snapshots in public/reports/YYYY-MM-DD/report.json.
// Results are memoized per build worker so the many static routes that need the
// archive do not re-read and re-parse every file.

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const reportsDir = path.join(process.cwd(), "public", "reports");

let datesCache: string[] | null = null;
const reportCache = new Map<string, DailyReport | null>();

export function isReportDate(value: string) {
  return DATE_PATTERN.test(value);
}

/** Archived session dates, oldest first. */
export function archivedDates(): string[] {
  if (datesCache) return datesCache;
  if (!fs.existsSync(reportsDir)) return (datesCache = []);
  datesCache = fs
    .readdirSync(reportsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && DATE_PATTERN.test(entry.name))
    .filter((entry) => fs.existsSync(path.join(reportsDir, entry.name, "report.json")))
    .map((entry) => entry.name)
    .sort();
  return datesCache;
}

/** Parsed archived report, or null when missing or malformed. */
export function archivedReport(date: string): DailyReport | null {
  if (!DATE_PATTERN.test(date)) return null;
  if (reportCache.has(date)) return reportCache.get(date) ?? null;
  let report: DailyReport | null = null;
  try {
    report = JSON.parse(fs.readFileSync(path.join(reportsDir, date, "report.json"), "utf8")) as DailyReport;
  } catch {
    report = null;
  }
  reportCache.set(date, report);
  return report;
}

export function archivedReports(): Array<{ date: string; report: DailyReport }> {
  return archivedDates()
    .map((date) => ({ date, report: archivedReport(date) }))
    .filter((entry): entry is { date: string; report: DailyReport } => entry.report !== null);
}

export function reportHeadline(report: DailyReport) {
  return decodeText(report.narrative?.editorial?.headline ?? report.narrative?.daily_takeaway?.what_moved ?? "Completed U.S. market session");
}
