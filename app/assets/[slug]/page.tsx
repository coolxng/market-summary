import report from "../../../data/report_snapshot.json";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import SiteHeader from "../../components/SiteHeader";
import FooterLinks from "../../components/FooterLinks";
import TickerStrip from "../../components/TickerStrip";
import CatalystList from "../../components/CatalystList";
import WatchToggle from "../../components/WatchToggle";
import KeyboardShortcuts from "../../components/KeyboardShortcuts";
import AssetRangeChart, { type RangeKey } from "./AssetRangeChart";
import AssetQuote, { AssetHoverProvider } from "./AssetQuote";
import { assetBySlug, assetCatalog, isYieldAsset, logoUrl } from "../../lib/assets";
import { yearRange } from "../../lib/assetSummary";
import AssetLogo from "../../components/AssetLogo";
import { archivedReports } from "../../lib/archive";
import { historyPoints, intradayMinutes, sessionPoints, type ChartPoint } from "../../lib/chart";
import { catalystsOf, quoteRow, quoteSessionChart, verified, type AssetHistory, type DailyReport } from "../../lib/report";
import { formatBpsFromPoints, formatNumber, formatPct, formatSessionDate, toneClass } from "../../lib/format";
import styles from "./asset.module.css";

const dailyReport = report as unknown as DailyReport;
const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");
const OFF_US_CLOCK = new Set(["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "^N225", "^STOXX50E", "^FTSE", "^HSI"]);
const SOURCE_NAMES: Record<string, string> = { yahoo_finance: "Yahoo Finance", stooq: "Stooq (fallback)" };

export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return assetCatalog.map((asset) => ({ slug: asset.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const asset = assetBySlug[slug];
  if (!asset) return {};
  const title = `${asset.name} (${asset.symbol}) | The Daily Tape`;
  const description = `${asset.name} close, session range, multi-period performance, trend references and source-linked context from The Daily Tape.`;
  return {
    title,
    description,
    alternates: { canonical: `${siteUrl}/assets/${slug}/` },
    openGraph: { title, description, url: `${siteUrl}/assets/${slug}/`, type: "website" },
  };
}

function sectorName(source: DailyReport, symbol: string) {
  return Object.keys(source.daily_sector_performance ?? {}).find((name) => name.endsWith(`(${symbol})`));
}

/** One-day move for `symbol` in a given issue, plus a ranking note when it led or lagged. */
function issueMove(source: DailyReport, symbol: string): { move: number | null; note: string | null } {
  const row = verified(quoteRow(source, symbol));
  const sector = sectorName(source, symbol);
  const move = row?.pct_change ?? (sector ? source.daily_sector_performance[sector] : null) ?? null;
  let note: string | null = null;
  if (sector) {
    const ranked = Object.entries(source.daily_sector_performance).sort((a, b) => b[1] - a[1]);
    const rank = ranked.findIndex(([name]) => name === sector) + 1;
    note = rank === 1 ? "Top sector" : rank === ranked.length ? "Bottom sector" : `Sector rank ${rank} of ${ranked.length}`;
  } else if (source.mega_cap_data?.[symbol]) {
    const moves = Object.entries(source.mega_cap_data).map(([ticker, entry]) => [ticker, verified(entry.result)?.pct_change] as const)
      .filter((entry): entry is readonly [string, number] => entry[1] != null).sort((a, b) => b[1] - a[1]);
    if (moves[0]?.[0] === symbol) note = "Best in leadership sample";
    else if (moves.at(-1)?.[0] === symbol) note = "Weakest in leadership sample";
  }
  return { move, note };
}

function historyChange(history: AssetHistory | undefined, sessions: number, asYield: boolean) {
  const closes = history?.closes ?? [];
  if (closes.length <= sessions) return null;
  const last = closes.at(-1)!;
  const first = closes[closes.length - 1 - sessions];
  return asYield ? last - first : first ? ((last - first) / first) * 100 : null;
}

function ytdChange(history: AssetHistory | undefined, asYield: boolean) {
  if (!history?.dates.length) return null;
  const year = history.dates.at(-1)!.slice(0, 4);
  const start = history.dates.findIndex((date) => date.startsWith(year));
  // YTD is measured from the last close of the prior year when it is stored.
  const base = start > 0 ? start - 1 : null;
  if (base == null) return null;
  const first = history.closes[base];
  const last = history.closes.at(-1)!;
  return asYield ? last - first : first ? ((last - first) / first) * 100 : null;
}

function sliceHistory(history: AssetHistory | undefined, key: Exclude<RangeKey, "1D">): ChartPoint[] {
  if (!history?.closes.length) return [];
  const all = historyPoints(history.dates, history.closes);
  if (key === "YTD") {
    const year = history.dates.at(-1)!.slice(0, 4);
    const start = history.dates.findIndex((date) => date.startsWith(year));
    return start > 0 ? all.slice(start - 1) : [];
  }
  const count = { "5D": 6, "1M": 22, "3M": 64, "1Y": 253 }[key];
  return all.slice(-count);
}

export default async function AssetPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const asset = assetBySlug[slug];
  if (!asset) notFound();

  const asYield = isYieldAsset(asset);
  const row = verified(quoteRow(dailyReport, asset.symbol));
  const sector = sectorName(dailyReport, asset.symbol);
  const dayMove = row?.pct_change ?? (sector ? dailyReport.daily_sector_performance[sector] : null) ?? null;
  const session = quoteSessionChart(dailyReport, asset.symbol);
  const intraday = sessionPoints(session, !OFF_US_CLOCK.has(asset.symbol));
  // The last 5-minute bar opens at 3:55 PM; end U.S.-hours paths on the official
  // close so the chart, its header and the hover all finish on the published number.
  const closesAtBell = !OFF_US_CLOCK.has(asset.symbol) && !["Commodity", "FX", "Crypto"].includes(asset.category);
  const dayPoints = closesAtBell && row && intraday.points.length >= 3 && session?.session_date === row.session_date && intraday.points.at(-1)!.value !== row.end_price
    ? [...intraday.points, { label: "Official close", value: row.end_price }]
    : intraday.points;
  const history = dailyReport.asset_history?.[asset.symbol];
  const historyUsable = history && !history.error && history.closes.length > 1 ? history : undefined;
  const digits = asset.digits ?? 2;
  const format = { prefix: asset.pricePrefix, suffix: asset.priceSuffix, digits };
  const price = (value: number | null | undefined) => value == null ? "—" : `${asset.pricePrefix ?? ""}${formatNumber(value, digits)}${asset.priceSuffix ?? ""}`;
  const move = (value: number | null) => asYield ? formatBpsFromPoints(value) : formatPct(value);

  const allRanges: Array<{ key: RangeKey; points: ChartPoint[]; note: string }> = [
    {
      key: "1D",
      points: dayPoints,
      note: intradayMinutes(session?.source) ? `${intradayMinutes(session?.source)}-minute session path${intraday.zoneLabel ? ` · ${intraday.zoneLabel}` : ""}` : session?.source === "daily_5d_fallback" ? "Recent daily closes (no intraday path stored)" : session ? "Open and close only" : "No intraday path stored",
    },
    ...(["5D", "1M", "3M", "YTD", "1Y"] as const).map((key) => ({ key, points: sliceHistory(historyUsable, key), note: "Daily closes" })),
  ];
  // Offer only ranges with a drawable path; if none has one, keep them all so the chart's empty state explains why.
  const drawable = allRanges.filter((range) => range.points.length > 1);
  const ranges = drawable.length ? drawable : allRanges;
  const initial: RangeKey = dayPoints.length >= 3 ? "1D" : ranges.some((range) => range.key === "1M") ? "1M" : ranges[0].key;

  const performance: Array<[string, number | null]> = [
    ["1D", asYield ? row?.abs_change ?? null : dayMove],
    ["5D", historyChange(historyUsable, 5, asYield)],
    ["1M", historyChange(historyUsable, 21, asYield)],
    ["3M", historyChange(historyUsable, 63, asYield)],
    ["YTD", ytdChange(historyUsable, asYield)],
    ["1Y", historyChange(historyUsable, 252, asYield)],
  ];

  const catalysts = catalystsOf(dailyReport);
  const tagged = catalysts ? { ...catalysts, items: catalysts.items.filter((item) => (item.related_tickers ?? []).includes(asset.symbol)) } : undefined;

  const mentions = archivedReports()
    .slice()
    .reverse()
    .map(({ date, report: issue }) => ({ date, ...issueMove(issue, asset.symbol) }))
    .filter((entry) => entry.move != null)
    .slice(0, 8);

  const historyStale = historyUsable && historyUsable.as_of && historyUsable.as_of < dailyReport.session_date && !OFF_US_CLOCK.has(asset.symbol);
  const rowSource = row?.data_source ? SOURCE_NAMES[row.data_source] ?? row.data_source : "Yahoo Finance";
  const yearly = yearRange(asset.symbol, row?.end_price);
  const range52 = yearly && yearly.sessions >= 200 ? { ...yearly, position: yearly.high > yearly.low ? (yearly.last - yearly.low) / (yearly.high - yearly.low) : 0.5 } : null;
  const ma = historyUsable?.moving_averages ?? {};
  const above = historyUsable?.above_moving_average ?? {};

  return (
    <main id="main">
      <SiteHeader root="../../" current="asset" />
      <TickerStrip root="../../" />
      <div className={styles.page}>
        <AssetHoverProvider>
        <section className={styles.hero}>
          <nav className={styles.crumbs} aria-label="Breadcrumb"><a href="../../">Today</a><span aria-hidden="true">/</span><a href="../">Assets</a><span aria-hidden="true">/</span><span>{asset.symbol}</span></nav>
          <div className={styles.heroGrid}>
            <div>
              <p className={styles.kicker}>{asset.category.toUpperCase()} · {asset.symbol}</p>
              <h1 className={styles.title}>{logoUrl(asset) && <AssetLogo src={logoUrl(asset)} symbol={asset.symbol} size={64} />}<span>{asset.name}</span></h1>
              <p className={styles.sub}>
                {row ? `Closed at ${price(row.end_price)} on ${formatSessionDate(row.session_date ?? dailyReport.session_date, { weekday: "long", month: "short", day: "numeric" })}, ${asYield ? `${formatBpsFromPoints(row.abs_change)} on the day` : `${formatPct(row.pct_change)} on the day`}.`
                  : dayMove != null ? `${formatPct(dayMove)} on ${formatSessionDate(dailyReport.session_date, { weekday: "long", month: "short", day: "numeric" })}.` : "No verified close is stored for the latest session."}
              </p>
            </div>
            <AssetQuote
              className={styles.quote}
              label={row ? "LATEST CLOSE" : "LATEST SESSION"}
              value={row?.end_price ?? (historyUsable?.as_of === dailyReport.session_date ? historyUsable.closes.at(-1) ?? null : null)}
              change={asYield ? row?.abs_change ?? null : dayMove}
              changeUnit={asYield ? "bps" : "pct"}
              format={format}
            >
              <WatchToggle slug={asset.slug} name={asset.name} />
            </AssetQuote>
          </div>
        </section>

        <section className={styles.chartSection} aria-label={`${asset.name} price chart`}>
          <AssetRangeChart name={asset.name} ranges={ranges} initial={initial} format={format} changeUnit={asYield ? "bps" : "pct"} dayBase={row?.prev_close} latest={row?.end_price} action={<WatchToggle slug={asset.slug} name={asset.name} compact />} />
        </section>
        </AssetHoverProvider>

        <section className={styles.performance} aria-label="Multi-period performance">
          {performance.map(([label, value]) => (
            <div key={label}><span>{label}{asYield ? " (BPS)" : ""}</span><strong className={toneClass(value)}>{move(value)}</strong></div>
          ))}
        </section>

        <section className={styles.stats} aria-label="Session range and trend references">
          <div><span>OPEN</span><strong>{price(row?.session_open)}</strong></div>
          <div><span>DAY LOW</span><strong>{price(row?.day_low)}</strong></div>
          <div><span>DAY HIGH</span><strong>{price(row?.day_high)}</strong></div>
          <div><span>PREV CLOSE</span><strong>{price(row?.prev_close)}</strong></div>
          {(["20d", "50d", "200d"] as const).map((window) => (
            <div key={window}>
              <span>{window.toUpperCase()} AVG</span>
              <strong>{price(ma[window])}</strong>
              {above[window] != null && <small className={above[window] ? "positive" : "negative"}>{above[window] ? "Close above" : "Close below"}</small>}
            </div>
          ))}
        </section>

        {range52 && (
          <section className={styles.yearRange} aria-label="52-week range">
            <div className={styles.yearRangeHead}>
              <span>52-WEEK RANGE · DAILY CLOSES</span>
              <small>{range52.position >= 0.98 ? "At the top of its range" : range52.position <= 0.02 ? "At the bottom of its range" : `${Math.round(range52.position * 100)}% of the way from low to high`}</small>
            </div>
            <div className={styles.yearRangeBar}>
              <strong>{price(range52.low)}<small>LOW</small></strong>
              <div className={styles.track} role="img" aria-label={`Latest close ${price(range52.last)} between a 52-week low of ${price(range52.low)} and high of ${price(range52.high)}`}>
                <i style={{ width: `${range52.position * 100}%` }} />
                <b style={{ left: `${range52.position * 100}%` }} />
              </div>
              <strong>{price(range52.high)}<small>HIGH</small></strong>
            </div>
          </section>
        )}

        <section className={styles.context} aria-labelledby="asset-catalysts">
          <div className={styles.sectionHeading}>
            <div><p className={styles.kicker}>VERIFIED CATALYSTS</p><h2 id="asset-catalysts">Tagged to {asset.symbol}</h2></div>
            <p>Only developments whose publisher tagged {asset.symbol} are shown. They are context, not explanations for the price move.</p>
          </div>
          {tagged && tagged.items.length === 0
            ? <p className={styles.empty}>No development in the latest catalyst window was tagged to {asset.symbol} by its source.</p>
            : <CatalystList catalysts={tagged} assetBaseHref="../" />}
        </section>

        <section className={styles.context} aria-labelledby="asset-archive">
          <div className={styles.sectionHeading}>
            <div><p className={styles.kicker}>IN THE ARCHIVE</p><h2 id="asset-archive">Recent Daily Tape sessions</h2></div>
            <p>One-day moves recorded for {asset.symbol} in archived issues, newest first.</p>
          </div>
          {mentions.length ? (
            <ol className={styles.mentions}>
              {mentions.map((entry) => (
                <li key={entry.date}>
                  <a href={`../../reports/${entry.date}/`}>{formatSessionDate(entry.date, { weekday: "short", month: "short", day: "numeric", year: "numeric" })}</a>
                  <span>{entry.note ?? ""}</span>
                  <strong className={toneClass(entry.move)}>{formatPct(entry.move)}</strong>
                </li>
              ))}
            </ol>
          ) : <p className={styles.empty}>No archived issue recorded a verified move for {asset.symbol} yet.</p>}
        </section>

        <aside className={styles.sourceNote} aria-label="Source and freshness">
          <div><span>SOURCE</span><strong>{rowSource}{historyUsable ? ` · history ${historyUsable.source}` : ""}</strong></div>
          <p>
            Latest close and session range come from the {formatSessionDate(dailyReport.session_date, { month: "short", day: "numeric", year: "numeric" })} Close Tape
            {row?.session_date && row.session_date !== dailyReport.session_date ? ` (this market's latest local session: ${formatSessionDate(row.session_date, { month: "short", day: "numeric" })})` : ""}.
            Longer ranges use daily closes stored at generation, so this page makes no live requests.
            {asYield ? " Yield changes are shown in basis points." : ""}
            {asset.category === "Credit" ? " This is a bond ETF price, not a credit spread." : ""}
          </p>
          <span className={historyStale ? styles.warn : undefined}>
            {historyUsable?.as_of ? `HISTORY THROUGH ${formatSessionDate(historyUsable.as_of, { month: "short", day: "numeric", year: "numeric" }).toUpperCase()}${historyStale ? " · OLDER THAN REPORT SESSION" : ""}` : "LONGER-RANGE HISTORY NOT STORED YET"}
          </span>
        </aside>
        <footer className={styles.footer}>
          <div><strong>THE DAILY TAPE</strong><span>Signal over noise.</span><FooterLinks root="../../" /></div>
          <KeyboardShortcuts bindings={{
            "/": { kind: "href", href: "../../search/", label: "Search assets and archive" },
            h: { kind: "href", href: "../../", label: "Today's close" },
            a: { kind: "href", href: "../../reports/", label: "Report archive" },
            m: { kind: "href", href: "../../morning/", label: "Pre-Market brief" },
          }} />
        </footer>
      </div>
    </main>
  );
}
