import type { Metadata } from "next";
import snapshot from "../../data/morning_snapshot.json";
import report from "../../data/report_snapshot.json";
import MorningTape, { type MorningSnapshot } from "./MorningTape";
import { reportHeadline } from "../lib/archive";
import type { DailyReport } from "../lib/report";

export const metadata: Metadata = {
  title: "Morning Tape | The Daily Tape",
  description: "Premarket futures, overnight global markets, the official Treasury curve, today's calendar and source-linked catalysts before the U.S. session.",
  alternates: { canonical: "./morning/" },
  openGraph: {
    title: "Morning Tape | The Daily Tape",
    description: "Know the setup before the U.S. session starts.",
    url: "./morning/",
    type: "website",
  },
};

export default function MorningPage() {
  const latest = report as unknown as DailyReport;
  return <MorningTape snapshot={snapshot as unknown as MorningSnapshot} latestClose={{ date: latest.session_date, headline: reportHeadline(latest) }} />;
}
