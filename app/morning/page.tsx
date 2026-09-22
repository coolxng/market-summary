import type { Metadata } from "next";
import snapshot from "../../morning_snapshot.json";
import MorningClient, { type MorningSnapshot } from "./MorningClient";

export const metadata: Metadata = {
  title: "Morning Tape | The Daily Tape",
  description: "Premarket futures, cross-asset moves, global markets, calendar events, earnings, and source-linked headlines before the U.S. session.",
  alternates: { canonical: "./morning/" },
  openGraph: {
    title: "Morning Tape | The Daily Tape",
    description: "Know the setup before the U.S. session starts.",
    url: "./morning/",
    type: "website",
  },
};

export default function MorningPage() {
  return <MorningClient snapshot={snapshot as MorningSnapshot} />;
}
