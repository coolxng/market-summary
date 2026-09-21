import type { Metadata } from "next";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/";
const appleTouchIconUrl = new URL("apple-touch-icon.png", siteUrl).toString();
const favicon16Url = new URL("favicon-16x16.png", siteUrl).toString();
const favicon32Url = new URL("favicon-32x32.png", siteUrl).toString();

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "Market Summary — The Daily Tape",
  description: "A decisive, data-first read on the latest completed U.S. trading session across equities, rates, sectors, crypto, and global markets.",
  alternates: { canonical: "./" },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  icons: {
    icon: [
      { url: favicon32Url, type: "image/png", sizes: "32x32" },
      { url: favicon16Url, type: "image/png", sizes: "16x16" },
    ],
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
        <meta name="theme-color" content="#f3f0e7" />
        <link id="site-favicon" rel="icon" type="image/svg+xml" href={new URL("favicon-light.svg", siteUrl).toString()} />
        <script
          dangerouslySetInnerHTML={{
            __html:
              'try{var t=localStorage.getItem("daily-tape-theme");if(t==="ink"){document.documentElement.dataset.theme="ink";document.querySelector(\'meta[name="theme-color"]\').content="#080808";var i=document.getElementById("site-favicon");i.href=new URL("favicon-dark.svg",i.href).href}}catch(e){}',
          }}
        />
      </head>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema) }}
        />
        {children}
      </body>
    </html>
  );
}
