import type { Metadata } from "next";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "Market Summary — The Daily Tape",
  description: "A decisive, data-first read on the latest completed U.S. trading session across equities, rates, sectors, crypto, and global markets.",
  icons: { icon: "favicon.svg", shortcut: "favicon.svg" },
  openGraph: {
    title: "The Daily Tape",
    description: "The session closed. Here is what mattered.",
    type: "website",
    images: ["og.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "The Daily Tape",
    description: "The session closed. Here is what mattered.",
    images: ["og.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
