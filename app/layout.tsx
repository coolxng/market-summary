import type { Metadata } from "next";
import "./globals.css";
import PWARegister from "./components/PWARegister";
import { THEME_COLORS, THEME_STORAGE_KEY } from "./lib/theme";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/";
const appleTouchIconUrl = new URL("apple-touch-icon.png", siteUrl).toString();
const analyticsDomain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;
const analyticsSrc = process.env.NEXT_PUBLIC_PLAUSIBLE_SRC ?? "https://plausible.io/js/script.js";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "Market Summary — The Daily Tape",
  description: "A decisive, data-first read on the latest completed U.S. trading session across equities, rates, sectors, crypto, and global markets.",
  alternates: {
    canonical: "./",
    types: { "application/rss+xml": "./feed.xml" },
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  icons: {
    apple: [{ url: appleTouchIconUrl, type: "image/png", sizes: "180x180" }],
  },
  openGraph: {
    url: "./",
    siteName: "The Daily Tape",
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

const websiteSchema = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "The Daily Tape",
  url: siteUrl,
  description:
    "Automated market-close intelligence for the latest completed U.S. trading session across equities, sectors, rates, commodities, global markets, and crypto.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="theme-color" content={THEME_COLORS.paper} />
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)})==="ink"?"ink":"paper";document.documentElement.dataset.theme=t;var m=document.querySelector('meta[name="theme-color"]');if(m)m.content=t==="ink"?${JSON.stringify(THEME_COLORS.ink)}:${JSON.stringify(THEME_COLORS.paper)};var i=document.createElement("link");i.id="site-favicon";i.rel="icon";i.type="image/svg+xml";i.href=new URL(t==="ink"?"favicon-dark.svg":"favicon-light.svg",${JSON.stringify(siteUrl)}).href;document.head.appendChild(i)}catch(e){}`,
          }}
        />
      </head>
      <body>
        <a className="skip-link" href="#main">Skip to content</a>
        <PWARegister />
        {analyticsDomain && (
          <script defer data-domain={analyticsDomain} src={analyticsSrc} />
        )}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema) }}
        />
        {children}
      </body>
    </html>
  );
}
