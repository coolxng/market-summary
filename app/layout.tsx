import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:3000";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const base = new URL(`${protocol}://${host}`);
  return {
    metadataBase: base,
    title: "Market Summary — The Daily Tape",
    description: "A decisive, data-first read on the latest completed U.S. trading session across equities, rates, sectors, crypto, and global markets.",
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
    openGraph: {
      title: "The Daily Tape",
      description: "The session closed. Here is what mattered.",
      type: "website",
      images: [new URL("/og.png", base).toString()],
    },
    twitter: {
      card: "summary_large_image",
      title: "The Daily Tape",
      description: "The session closed. Here is what mattered.",
      images: [new URL("/og.png", base).toString()],
    },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
