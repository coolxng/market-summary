import type { Metadata } from "next";
import snapshot from "../../morning_snapshot.json";
import MorningTape, { type MorningSnapshot } from "./MorningTape";

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
  return <MorningTape snapshot={snapshot as unknown as MorningSnapshot} />;
}
