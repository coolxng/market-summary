import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import { assetCatalog } from "../lib/assets";
import SearchClient, { type SearchReport } from "./SearchClient";

export const metadata: Metadata = {
  title: "Search | The Daily Tape",
  description: "Search tracked markets and archived Daily Tape sessions.",
  alternates: { canonical: "./search/" },
};

const datePattern = /^\d{4}-\d{2}-\d{2}$/;

function displayDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T12:00:00Z`));
}

function reports(): SearchReport[] {
  const dir = path.join(process.cwd(), "public", "reports");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && datePattern.test(entry.name))
    .map((entry) => {
      const file = path.join(dir, entry.name, "report.json");
      if (!fs.existsSync(file)) return null;
      try {
        const snapshot = JSON.parse(fs.readFileSync(file, "utf8")) as {
          narrative?: { editorial?: { headline?: string }; daily_takeaway?: { what_moved?: string } };
        };
        return {
          date: entry.name,
          displayDate: displayDate(entry.name),
          headline: snapshot.narrative?.editorial?.headline ?? snapshot.narrative?.daily_takeaway?.what_moved ?? "Completed U.S. market session",
        };
      } catch {
        return null;
      }
    })
    .filter((item): item is SearchReport => item !== null)
    .sort((a, b) => b.date.localeCompare(a.date));
}

export default function SearchPage() {
  return (
    <SearchClient
      assets={assetCatalog.map(({ slug, symbol, name, category }) => ({ slug, symbol, name, category }))}
      reports={reports()}
    />
  );
}
