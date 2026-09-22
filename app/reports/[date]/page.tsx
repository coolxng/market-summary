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

function readReport(date: string): DailyReport | null {
  if (!datePattern.test(date)) return null;
  const file = reportPath(date);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf8")) as DailyReport;
}

export function generateStaticParams() {
  const dir = reportsDir();
  if (!fs.existsSync(dir)) return [];

  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && datePattern.test(entry.name))
    .filter((entry) => fs.existsSync(reportPath(entry.name)))
    .map((entry) => ({ date: entry.name }));
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

  return <DailyTape report={report} archived archiveHref="../" homeHref="../../" assetBaseHref="../../assets/" />;
}
