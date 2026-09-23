import report from "../../data/report_snapshot.json";
import type { Metadata } from "next";
import SiteHeader from "../components/SiteHeader";
import Breadcrumbs from "../components/Breadcrumbs";
import FooterLinks from "../components/FooterLinks";
import AssetLogo from "../components/AssetLogo";
import TickerStrip from "../components/TickerStrip";
import AssetsBrowser, { type AssetGroup } from "./AssetsBrowser";
import { assetCatalog, assetCategories, type AssetDefinition } from "../lib/assets";
import { assetSummaries, topMovers, type AssetSummary } from "../lib/assetSummary";
import { formatSessionDate } from "../lib/format";
import type { DailyReport } from "../lib/report";
import styles from "./assets.module.css";

const dailyReport = report as unknown as DailyReport;
const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");

export const metadata: Metadata = {
  title: "Assets | The Daily Tape",
  description: "Every market The Daily Tape tracks: indexes, stocks, ETFs, rates, commodities and crypto, with the latest close and one-day move.",
  alternates: { canonical: `${siteUrl}/assets/` },
};

const CATEGORY_TITLES: Record<AssetDefinition["category"], string> = {
  Index: "Indexes",
  Equity: "Stocks",
  ETF: "ETFs",
  "Sector ETF": "Sectors",
  Rates: "Rates",
  Credit: "Credit",
  Volatility: "Volatility",
  FX: "Currencies",
  Commodity: "Commodities",
  Crypto: "Crypto",
};

function anchorOf(category: string) {
  return category.toLowerCase().replace(/\s+/g, "-");
}

function Mover({ asset }: { asset: AssetSummary }) {
  return (
    <a className={styles.mover} href={`./${asset.slug}/`}>
      <AssetLogo src={asset.logo} symbol={asset.symbol} size={30} />
      <span className={styles.moverName}><strong>{asset.symbol.replace(/^\^/, "").replace(/=F$|-USD$/, "")}</strong><small>{asset.name}</small></span>
      <span className={styles.moverQuote}><b className={asset.tone}>{asset.changeText}</b><small>{asset.priceText}</small></span>
    </a>
  );
}

export default function AssetsPage() {
  const groups: AssetGroup[] = assetCategories
    .map((category) => ({
      id: anchorOf(category),
      title: CATEGORY_TITLES[category],
      changeLabel: category === "Rates" ? "1D (BPS)" : "1D",
      rows: assetSummaries.filter((summary) => summary.category === category),
    }))
    .filter((group) => group.rows.length);
  const movers = topMovers(3);
  const session = formatSessionDate(dailyReport.session_date, { weekday: "long", month: "long", day: "numeric", year: "numeric" });

  return (
    <main id="main">
      <SiteHeader root="../" current="asset" />
      <TickerStrip root="../" />
      <div className={styles.page}>
        <section className={styles.hero}>
          <Breadcrumbs items={[{ label: "Today", href: "../" }, { label: "Assets" }]} />
          <p className={styles.kicker}>MARKETS TRACKED · {assetCatalog.length} ASSETS</p>
          <h1>Every market on the tape.</h1>
          <span className={styles.sub}>Latest close and one-day move from the {session} session. Open any asset for its price history, trend references and archive record.</span>
        </section>

        {(movers.gainers.length > 0 || movers.losers.length > 0) && (
          <section className={styles.movers} aria-label="Biggest one-day moves">
            <div>
              <p className={styles.moversLabel}>TOP GAINERS</p>
              <div className={styles.moverList}>{movers.gainers.map((asset) => <Mover key={asset.slug} asset={asset} />)}</div>
            </div>
            <div>
              <p className={styles.moversLabel}>TOP LOSERS</p>
              <div className={styles.moverList}>{movers.losers.map((asset) => <Mover key={asset.slug} asset={asset} />)}</div>
            </div>
          </section>
        )}

        <nav className={styles.jump} aria-label="Asset categories">
          {groups.map((group) => (
            <a key={group.id} href={`#${group.id}`}>{group.title}<small>{group.rows.length}</small></a>
          ))}
          <a className={styles.search} href="../search/">Search <span aria-hidden="true">/</span></a>
        </nav>

        <AssetsBrowser groups={groups} all={assetSummaries} />

        <footer className={styles.footer}>
          <div><strong>THE DAILY TAPE</strong><span>Signal over noise.</span></div>
          <FooterLinks root="../" />
        </footer>
      </div>
    </main>
  );
}
