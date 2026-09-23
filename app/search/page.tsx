import type { Metadata } from "next";
import { assetSummaries } from "../lib/assetSummary";
import SearchClient, { type SearchReport } from "./SearchClient";
import { archivedReports, reportHeadline } from "../lib/archive";
import { formatSessionDate } from "../lib/format";

export const metadata: Metadata = {
  title: "Search | The Daily Tape",
  description: "Search tracked markets and archived Daily Tape sessions.",
  alternates: { canonical: "./search/" },
};

function reports(): SearchReport[] {
  return archivedReports()
    .map(({ date, report }) => ({ date, displayDate: formatSessionDate(date), headline: reportHeadline(report) }))
    .reverse();
}

export default function SearchPage() {
  return (
    <SearchClient
      assets={assetSummaries}
      reports={reports()}
    />
  );
}
