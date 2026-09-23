import ShareSummaryButton from "./components/ShareSummaryButton";
import DeliveryPanel from "./components/DeliveryPanel";
import WatchlistPanel, { type WatchAsset } from "./components/WatchlistPanel";
import SiteHeader from "./components/SiteHeader";
import ReportNav, { type ReportChapter } from "./components/ReportNav";
import Breadcrumbs from "./components/Breadcrumbs";
import PublicationBanner from "./components/PublicationBanner";
import KeyboardShortcuts from "./components/KeyboardShortcuts";
import PriceChart from "./components/PriceChart";
import SectionShare from "./components/SectionShare";
import MarketInternals from "./components/MarketInternals";
import RatesCredit from "./components/RatesCredit";
import RegimeStrip from "./components/RegimeStrip";
import RelativeStrength from "./components/RelativeStrength";
import { sessionPoints } from "./lib/chart";
import MarketCalendarList from "./components/MarketCalendarList";
import CatalystList from "./components/CatalystList";
import DataStatus, { FeedHealthList, dataStatusLabel } from "./components/DataStatus";
import { assetCatalog, assetBySymbol } from "./lib/assets";
import {
  calendarOf,
  catalystsOf,
  verified,
  type DailyReport,
  type MarketDatum,
  type SessionChart,
} from "./lib/report";
import { decodeText, formatBpsFromPoints, formatNumber, formatPct, formatPp, formatSessionDate, toneClass } from "./lib/format";
import { classifyRegime, REGIME_LABEL, type RegimeEntry } from "./lib/regime";

export type { DailyReport } from "./lib/report";

// Five numbered chapters plus the opening brief. IDs here are chapter anchors;
// the older section anchors (#scorecard, #sectors, #macro, #rates, #calendar,
// #ahead …) are kept on the subsections inside them so shared links still work.
const chapters: ReportChapter[] = [
  { id: "brief", label: "Brief" },
  { id: "overview", label: "Overview", number: "01" },
  { id: "leadership", label: "Leadership", number: "02" },
  { id: "drivers", label: "Drivers", number: "03" },
  { id: "cross-asset", label: "Macro", number: "04" },
  { id: "next-session", label: "Ahead", number: "05" },
];

const globalMarkets = [
  ["^N225", "Nikkei 225", "Japan"],
  ["^STOXX50E", "Euro Stoxx 50", "Europe"],
  ["^FTSE", "FTSE 100", "United Kingdom"],
  ["^HSI", "Hang Seng", "Hong Kong"],
] as const;

const cryptoMarkets = [
  ["BTC-USD", "Bitcoin", "BTC", "btc"],
  ["ETH-USD", "Ethereum", "ETH", "eth"],
  ["SOL-USD", "Solana", "SOL", "sol"],
  ["XRP-USD", "XRP", "XRP", "xrp"],
] as const;

const megaCapNames: Record<string, string> = {
  AAPL: "Apple",
  MSFT: "Microsoft",
  NVDA: "Nvidia",
  AMZN: "Amazon",
  META: "Meta Platforms",
  SNDK: "SanDisk",
  AMD: "Advanced Micro Devices",
  INTC: "Intel",
  MU: "Micron Technology",
};

const megaCapLogoSlugs: Record<string, string> = {
  AAPL: "apple",
  MSFT: "microsoft",
  NVDA: "nvidia",
  AMZN: "amazon",
  META: "meta-platforms",
  SNDK: "sandisk",
  AMD: "advanced-micro-devices",
  INTC: "intel",
  MU: "micron-technology",
};

function sectorLabel(value: string) {
  return value.replace(/\s*\([A-Z]+\)$/, "");
}

function sectorSymbol(value: string) {
  return value.match(/\(([A-Z]+)\)$/)?.[1];
}

function splitHeadline(value: string) {
  const words = value.trim().split(/\s+/);
  if (words.length < 4) return { lead: value, accent: "" };
  const accentCount = Math.min(3, Math.max(2, Math.ceil(words.length / 2)));
  return { lead: words.slice(0, -accentCount).join(" "), accent: words.slice(-accentCount).join(" ") };
}

function isoWeek(value: Date) {
  const date = new Date(Date.UTC(value.getUTCFullYear(), value.getUTCMonth(), value.getUTCDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil((((date.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
}

function axisLabels(times: string[]) {
  return [times[0], times[Math.floor(times.length / 2)], times.at(-1)].filter(Boolean) as string[];
}

function Sparkline({ values, positive, label }: { values: number[]; positive: boolean; label?: string }) {
  if (values.length < 2) return <div className="spark-empty">No verified path</div>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 100},${38 - ((value - min) / span) * 30}`).join(" ");
  return (
    <svg className="sparkline" viewBox="0 0 100 42" preserveAspectRatio="none" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <polyline points={points} fill="none" stroke={positive ? "var(--up)" : "var(--down)"} strokeWidth="2.25" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function pathLabel(name: string, values: number[], digits = 2) {
  if (values.length < 2) return undefined;
  return `${name} path: ${formatNumber(values[0], digits)} to ${formatNumber(values.at(-1), digits)}, low ${formatNumber(Math.min(...values), digits)}, high ${formatNumber(Math.max(...values), digits)}.`;
}

function IndexCard({ item, chart, name, short, slug, assetBaseHref, currency = false, digits = 2, suffix = "" }: {
  item: MarketDatum | undefined; chart?: SessionChart; name: string; short: string; slug: string; assetBaseHref: string; currency?: boolean; digits?: number; suffix?: string;
}) {
  const row = verified(item);
  const values = row ? (chart?.closes?.length ? chart.closes : row.closes) : [];
  return (
    <article className="index-card">
      <div className="card-topline">
        <span className="eyebrow">{short}</span>
        <span className={`move ${toneClass(row?.pct_change)}`}>{row ? formatPct(row.pct_change) : "UNAVAILABLE"}</span>
      </div>
      <div className="index-value">{row ? `${currency ? "$" : ""}${formatNumber(row.end_price, digits)}${suffix}` : "—"}</div>
      <div className="index-name">{name}</div>
      <a className="asset-card-link" href={`${assetBaseHref}${slug}/`}>Open asset →</a>
      <Sparkline values={values} positive={(row?.pct_change ?? 0) >= 0} label={pathLabel(name, values, digits)} />
    </article>
  );
}

function Signal({ label, value, note, tone }: { label: string; value: string; note: string; tone: "good" | "warn" | "neutral" }) {
  return (
    <div className="signal-row">
      <span className={`signal-dot ${tone}`} aria-hidden="true" />
      <div><span className="signal-label">{label}</span><span className="signal-note">{note}</span></div>
      <strong>{value}</strong>
    </div>
  );
}

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");

type Share = { url: string; title: string };

/** Subsection heading. The kicker names the parent chapter so deep links keep their context. */
function SectionHeading({ id, chapter, kicker, title, children, share, lead = false }: { id?: string; chapter: string; kicker: string; title: React.ReactNode; children?: React.ReactNode; share?: Share; lead?: boolean }) {
  return (
    <div className={`section-heading${lead ? " section-heading--lead" : ""}`}>
      <div>
        <p className="section-kicker"><span className="section-kicker__chapter">{chapter}</span><span>{kicker}</span></p>
        <h3 id={id ? `${id}-title` : undefined}>{title}</h3>
      </div>
      {(children || share) && <div className="section-heading__aside">{children && <p>{children}</p>}{share && <SectionShare url={share.url} title={share.title} />}</div>}
    </div>
  );
}

/** A primary report chapter, opened by an ink section-front band and the chapter's question. */
function Chapter({ id, number, title, dek, contents, children, className = "" }: { id: string; number: string; title: string; dek: string; contents: Array<[anchor: string, label: string]>; children: React.ReactNode; className?: string }) {
  return (
    <section className={`report-chapter ${className}`.trim()} id={id} aria-labelledby={`${id}-title`}>
      <header className="report-chapter__header">
        <div className="report-chapter__band">
          <p className="report-chapter__number"><span className="visually-hidden">Chapter </span>{number}</p>
          <h2 id={`${id}-title`}>{title}</h2>
          <nav className="report-chapter__contents" aria-label={`${title}: sections`}>
            <ul>{contents.map(([anchor, label]) => <li key={anchor}><a href={`#${anchor}`}>{label}</a></li>)}</ul>
          </nav>
        </div>
        <p className="report-chapter__dek">{dek}</p>
      </header>
      <div className="report-chapter__body">{children}</div>
    </section>
  );
}

export type ArchiveComparison = {
  sampleSize: number;
  breadthAverage: number | null;
  breadthDelta: number | null;
  vixPercentile: number | null;
  regimeStreak: number;
  sp500FiveSessionReturn: number | null;
  topSector: string | null;
  topSectorStreak: number;
  topSectorLedCount: number;
  topSectorWindow: number;
};

export default function DailyTape({
  report,
  archived = false,
  archiveHref = "./reports/",
  assetBaseHref = "./assets/",
  previousReportHref,
  nextReportHref,
  archiveComparison,
  regimeTimeline = [],
  regimeHrefBase,
}: {
  report: DailyReport;
  archived?: boolean;
  archiveHref?: string;
  assetBaseHref?: string;
  previousReportHref?: string;
  nextReportHref?: string;
  archiveComparison?: ArchiveComparison;
  regimeTimeline?: RegimeEntry[];
  regimeHrefBase?: string;
}) {
  const dailyReport = report;
  const market = dailyReport.market_data;
  const siteRoot = archived ? "../../" : "./";
  const searchHref = `${siteRoot}search/`;

  const sectorEntries = Object.entries(dailyReport.daily_sector_performance).sort((a, b) => b[1] - a[1]);
  const sectorAbsMax = Math.max(0.01, ...sectorEntries.map(([, value]) => Math.abs(value)));
  const topSector = sectorEntries[0];
  const bottomSector = sectorEntries[sectorEntries.length - 1];
  const megaCaps = Object.keys(megaCapNames).map((ticker) => {
    const snapshot = dailyReport.mega_cap_data?.[ticker];
    const item = verified(snapshot?.result);
    const chart = snapshot?.session_chart;
    return {
      ticker,
      name: snapshot?.name ?? megaCapNames[ticker],
      item,
      chartValues: item ? (chart?.closes?.length ? chart.closes : item.closes) : [],
      chartAxis: axisLabels(chart?.times?.length ? chart.times : ["9:30 AM", "4:00 PM"]),
      chartSource: chart?.source,
    };
  });

  const editorial = dailyReport.narrative.editorial;
  const headline = decodeText(editorial?.headline ?? (topSector ? `${sectorLabel(topSector[0])} led the sector ranking.` : "The session closed."));
  const headlineParts = splitHeadline(headline);
  const sp = verified(market["^GSPC"]);
  const nasdaq = verified(market["^IXIC"]);
  const russell = verified(market["^RUT"]);
  const vix = verified(market["^VIX"]);
  const tenYear = verified(market["^TNX"]);
  const tBill = verified(market["^IRX"]);
  const dxy = verified(market["DX-Y.NYB"]);
  const gold = verified(market["GC=F"]);
  const oil = verified(market["CL=F"]);
  const breadth = dailyReport.daily_market_breadth;
  const sessionDate = new Date(`${dailyReport.session_date}T12:00:00Z`);
  const dateRange = `${formatSessionDate(dailyReport.previous_session_date, { month: "short", day: "numeric" })} — ${formatSessionDate(dailyReport.session_date, { month: "short", day: "numeric", year: "numeric" })}`;
  const issue = `${String(sessionDate.getUTCFullYear()).slice(-2)}.${String(isoWeek(sessionDate)).padStart(2, "0")}`;
  const generatedLabel = new Date(dailyReport.generated_at).toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" });
  const sectorTotal = sectorEntries.length;
  const breadthTone = breadth.positive_sector_share >= 60 ? "Broad" : breadth.positive_sector_share >= 45 ? "Mixed" : "Narrow";
  const regime = classifyRegime(dailyReport);
  const riskTone = REGIME_LABEL[regime.regime];
  const equalWeightGap = breadth.rsp_pct_change != null && breadth.spy_pct_change != null ? breadth.rsp_pct_change - breadth.spy_pct_change : null;
  const capWeightMessage = equalWeightGap === null
    ? "The equal-weight comparison is unavailable for this session."
    : Math.abs(equalWeightGap) < 0.005 ? "Equal-weight and cap-weight returns matched."
    : `${equalWeightGap > 0 ? "Equal weight" : "Cap weight"} outperformed by ${Math.abs(equalWeightGap).toFixed(2)} percentage points. This is a participation proxy, not an attribution of index contributions.`;
  const thesisQuote = editorial?.regime.interpretation ?? capWeightMessage;
  const spChart = dailyReport.session_charts["^GSPC"];
  const spPoints = sp ? sessionPoints(spChart, true).points : [];
  const decisionSummary = [
    ["Observed", decodeText(dailyReport.narrative.daily_takeaway.what_moved)],
    ["Interpretation", decodeText(dailyReport.narrative.daily_takeaway.why)],
    ["Next-session checks", decodeText(dailyReport.narrative.daily_takeaway.what_to_watch)],
  ];
  const outlookItems: Array<[string, string, string[]]> = [
    ["01", "Cross-asset checks", dailyReport.narrative.next_session_outlook.macro],
    ["02", "Rates & confirmation", dailyReport.narrative.next_session_outlook.fed_policy],
    ["03", "Technology leadership", dailyReport.narrative.next_session_outlook.earnings_and_catalysts],
    ["04", "Risk dashboard", dailyReport.narrative.next_session_outlook.risk_factors],
  ];

  const calendar = calendarOf(dailyReport);
  const catalysts = catalystsOf(dailyReport);
  const quality = dailyReport.data_quality;
  const allFeeds = [...(calendar?.feeds ?? []), ...(catalysts?.feeds ?? [])];

  // Watchlist rows carry only this session's 1D move; nothing else is substituted.
  const watchAssets: WatchAsset[] = assetCatalog.map((asset) => {
    const direct = verified(market[asset.symbol] ?? dailyReport.mega_cap_data?.[asset.symbol]?.result ?? dailyReport.sector_data?.[asset.symbol]);
    const sectorReturn = Object.entries(dailyReport.daily_sector_performance).find(([name]) => sectorSymbol(name) === asset.symbol)?.[1];
    const history = dailyReport.asset_history?.[asset.symbol];
    const historyClose = history?.as_of === dailyReport.session_date ? history.closes.at(-1) ?? null : null;
    const asYield = asset.category === "Rates" && asset.priceSuffix === "%";
    return {
      slug: asset.slug,
      symbol: asset.symbol,
      name: asset.name,
      category: asset.category,
      price: direct?.end_price ?? historyClose,
      change: asYield ? direct?.abs_change ?? null : direct?.pct_change ?? sectorReturn ?? null,
      changeUnit: asYield ? "bps" : "pct",
      pricePrefix: asset.pricePrefix,
      priceSuffix: asset.priceSuffix,
      digits: asset.digits,
      spark: history && !history.error ? history.closes.slice(-22) : [],
      catalysts: (catalysts?.items ?? []).filter((item) => (item.related_tickers ?? []).includes(asset.symbol)).length,
      localCalendar: asset.category === "Crypto" || ["^N225", "^STOXX50E", "^FTSE", "^HSI"].includes(asset.symbol),
      otherSession: direct?.session_date && direct.session_date !== dailyReport.session_date ? formatSessionDate(direct.session_date, { month: "short", day: "numeric" }) : null,
    };
  });

  const tenYearChange = tenYear?.abs_change ?? null;
  const permalink = `${SITE_URL}/reports/${dailyReport.session_date}/`;
  const shareDate = formatSessionDate(dailyReport.session_date, { month: "short", day: "numeric", year: "numeric" });
  const shareFor = (anchor: string, section: string) => ({ url: `${permalink}#${anchor}`, title: `The Daily Tape · ${shareDate} · ${section}` });

  const editionShort = formatSessionDate(dailyReport.session_date, { month: "short", day: "numeric" });
  const editionLong = formatSessionDate(dailyReport.session_date, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  const reportLinks = chapters.map(({ id, label }) => ({ href: `#${id}`, label }));
  const hasRelativeStrength = Boolean(dailyReport.relative_strength?.rows?.length);
  const hasArchiveContext = Boolean(archived && archiveComparison && archiveComparison.sampleSize > 0);

  return (
    <main id="main">
      <SiteHeader root={siteRoot} current={archived ? "reports" : "close"} reportLinks={reportLinks} />
      <ReportNav
        chapters={chapters}
        edition={`${editionShort} close`}
        archived={archived}
        latestHref={archived ? siteRoot : undefined}
        status={archived ? undefined : <PublicationBanner compact sessionDate={dailyReport.session_date} generatedAt={dailyReport.generated_at} />}
      />

      <div className="page" id="top">
        <section className="report-opening" id="brief" aria-label={`The brief: ${archived ? "archived" : "latest"} Daily Tape for ${editionLong}`}>
          {archived && (
            <div className="archive-banner">
              <Breadcrumbs items={[{ label: "Close Tape", href: siteRoot }, { label: "Reports", href: archiveHref }, { label: shareDate }]} />
              <div className="archive-banner__body" role="note">
                <div>
                  <span className="archive-banner__label">Archived edition</span>
                  <strong>You are reading the {editionLong} close.</strong>
                  <p>Figures are exactly as published after that session and are never revised. The current report lives on the Close Tape.</p>
                </div>
                <a className="archive-banner__latest" href={siteRoot}>Go to the latest Daily Tape →</a>
              </div>
              <nav className="archive-session-nav" aria-label="Archived session navigation">
                <span>{previousReportHref ? <a href={previousReportHref} rel="prev">← Previous session</a> : <i>Earliest archived session</i>}</span>
                <a href={archiveHref}>All reports</a>
                <span>{nextReportHref ? <a href={nextReportHref} rel="next">Next session →</a> : <i>Latest archived session</i>}</span>
              </nav>
            </div>
          )}
          <div className="hero-grid hero">
            <div className="hero-copy">
              <div className="opening-meta">
                <p className="issue-line">
                  <span className="issue-line__edition">{archived ? "ARCHIVED DAILY TAPE" : "DAILY MARKET INTELLIGENCE"}</span>
                  <span>Issue {issue}</span>
                  <time dateTime={dailyReport.session_date} title={`Previous close to latest close: ${dateRange}`}>{shareDate}</time>
                  {!archived && <PublicationBanner compact className="issue-line__publication" sessionDate={dailyReport.session_date} generatedAt={dailyReport.generated_at} />}
                </p>
                <DataStatus sessionDate={dailyReport.session_date} quality={quality} />
              </div>
              <h1>
                {headlineParts.lead}
                {headlineParts.accent && <em>{headlineParts.accent}</em>}
              </h1>
              <p className="dek">{decodeText(editorial?.opening_summary ?? dailyReport.narrative.daily_takeaway.what_moved)}</p>
              <div className="hero-tags">
                <span className={`tag ${sp && sp.pct_change >= 0 ? "up" : "down"}`}>S&amp;P {formatPct(sp?.pct_change)}</span>
                <span className="tag neutral">Breadth {breadth.advances}/{sectorTotal}</span>
                <span className={`tag ${vix && vix.pct_change <= 0 ? "up" : "down"}`}>VIX {formatPct(vix?.pct_change)}</span>
                <SectionShare {...shareFor("brief", "The one-line read")} label="Copy link" />
                <ShareSummaryButton
                  headline={headline}
                  session={dateRange}
                  metrics={{
                    sp500: formatPct(sp?.pct_change),
                    nasdaq: formatPct(nasdaq?.pct_change),
                    vix: formatNumber(vix?.end_price),
                    breadth: `${breadth.positive_sector_share.toFixed(1)}%`,
                  }}
                />
              </div>
            </div>
            <aside className="regime-card" id="regime-monitor" aria-label="Market regime signals">
              <div className="regime-heading"><span>REGIME MONITOR</span><span className="regime-heading__tools"><span className="live-dot">SESSION CLOSED</span><SectionShare {...shareFor("regime-monitor", "Regime monitor")} /></span></div>
              <Signal label="Risk appetite" value={riskTone} note={`S&P ${formatPct(sp?.pct_change)} · VIX ${formatNumber(vix?.end_price)}`} tone={regime.regime === "constructive" ? "good" : regime.regime === "unavailable" ? "neutral" : "warn"} />
              <Signal label="Participation" value={breadthTone} note={`${breadth.advances} of ${sectorTotal} sectors advanced`} tone={breadthTone === "Broad" ? "good" : "warn"} />
              <Signal
                label="Rates impulse"
                value={tenYearChange == null ? "—" : tenYearChange < 0 ? "Easing" : tenYearChange > 0 ? "Tightening" : "Flat"}
                note={`10Y ${formatNumber(tenYear?.end_price)}% · ${formatBpsFromPoints(tenYearChange)}`}
                tone={tenYearChange == null || tenYearChange === 0 ? "neutral" : tenYearChange < 0 ? "good" : "warn"}
              />
              <Signal
                label="Dollar impulse"
                value={!dxy ? "—" : dxy.pct_change < 0 ? "Easing" : dxy.pct_change > 0 ? "Firming" : "Flat"}
                note={`DXY ${formatNumber(dxy?.end_price)} · ${formatPct(dxy?.pct_change)}`}
                tone={!dxy || dxy.pct_change === 0 ? "neutral" : dxy.pct_change < 0 ? "good" : "warn"}
              />
            </aside>
          </div>

          <div className="digest-strip" role="group" aria-label="Three-point market digest">
            <article><span>01 / MARKET</span><strong>{riskTone} close</strong><p>S&amp;P {formatPct(sp?.pct_change)}; Nasdaq {formatPct(nasdaq?.pct_change)}; VIX ended at {formatNumber(vix?.end_price)}.</p></article>
            <article><span>02 / LEADERSHIP</span><strong>{topSector && bottomSector ? `${sectorLabel(topSector[0])} over ${sectorLabel(bottomSector[0])}` : "Sector data unavailable"}</strong><p>{topSector && bottomSector ? `A ${Math.abs(topSector[1] - bottomSector[1]).toFixed(2)}-point spread separated the best and worst sectors.` : "Sector returns were not verified."}</p></article>
            <article><span>03 / INTERNALS</span><strong>{breadthTone} breadth</strong><p>{capWeightMessage}</p></article>
          </div>

          <section className="opening-tape scorecard" id="scorecard" aria-labelledby="scorecard-title">
            <SectionHeading id="scorecard" chapter="Brief" kicker="The tape" title="The tape, at a glance" share={shareFor("scorecard", "Scorecard")}>Previous close to latest close. Sparklines show the verified regular-hours session path when available.</SectionHeading>
            <div className="index-grid">
              <IndexCard item={market["^GSPC"]} chart={dailyReport.session_charts["^GSPC"]} name="S&P 500" short="SPX" slug="spx" assetBaseHref={assetBaseHref} />
              <IndexCard item={market["^IXIC"]} chart={dailyReport.session_charts["^IXIC"]} name="Nasdaq Composite" short="COMP" slug="nasdaq" assetBaseHref={assetBaseHref} />
              <IndexCard item={market["^DJI"]} chart={dailyReport.session_charts["^DJI"]} name="Dow Jones" short="DJIA" slug="dow" assetBaseHref={assetBaseHref} />
              <IndexCard item={market["^VIX"]} chart={dailyReport.session_charts["^VIX"]} name="CBOE Volatility" short="VIX" slug="vix" assetBaseHref={assetBaseHref} />
              <IndexCard item={market["^TNX"]} chart={dailyReport.session_charts["^TNX"]} name="10-Year Treasury" short="10Y" slug="us-10y" assetBaseHref={assetBaseHref} suffix="%" />
              <IndexCard item={market["DX-Y.NYB"]} chart={dailyReport.session_charts["DX-Y.NYB"]} name="U.S. Dollar Index" short="DXY" slug="dxy" assetBaseHref={assetBaseHref} />
              <IndexCard item={market["BTC-USD"]} chart={dailyReport.session_charts["BTC-USD"]} name="Bitcoin" short="BTC" slug="bitcoin" assetBaseHref={assetBaseHref} currency digits={0} />
              <IndexCard item={market["ETH-USD"]} chart={dailyReport.session_charts["ETH-USD"]} name="Ethereum" short="ETH" slug="ethereum" assetBaseHref={assetBaseHref} currency digits={0} />
            </div>
          </section>
        </section>

        <Chapter
          id="overview"
          number="01"
          title="Overview"
          dek="How today fits the recent run of sessions, and the markets you follow."
          contents={[
            ...(regimeTimeline.length ? [["regime", "Regime history"] as [string, string]] : []),
            ...(hasArchiveContext ? [["context", "Historical context"] as [string, string]] : []),
            ...(!archived ? [["watchlist", "Your watchlist"] as [string, string]] : []),
          ]}
        >
          {regimeTimeline.length > 0 && (
            <section className="report-subsection regime-history" id="regime" aria-labelledby="regime-title">
              <div className="regime-history__head">
                <p className="section-kicker"><span className="section-kicker__chapter">Overview</span><span>Regime history</span></p>
                <h3 id="regime-title">How the tape has read</h3>
                <p>Today&apos;s regime in the context of recent sessions. Select a day to see its inputs.</p>
              </div>
              <RegimeStrip entries={regimeTimeline} hrefBase={regimeHrefBase} rule={dailyReport.regime_history?.rule} />
            </section>
          )}

          {hasArchiveContext && archiveComparison && (
            <section className="report-subsection archive-context" id="context" aria-labelledby="context-title">
              <SectionHeading id="context" chapter="Overview" kicker="Historical context" title="How this session compared">Context is calculated only from earlier archived Daily Tape sessions, so the comparison never uses future data.</SectionHeading>
              <div className="archive-context-grid">
                <article>
                  <span>BREADTH VS PRIOR AVG</span>
                  <strong>{formatPp(archiveComparison.breadthDelta, 1)}</strong>
                  <p>{archiveComparison.breadthAverage == null ? "Prior breadth unavailable." : `Prior ${archiveComparison.sampleSize}-session average: ${archiveComparison.breadthAverage.toFixed(1)}%`}</p>
                </article>
                <article>
                  <span>VIX SAMPLE RANK</span>
                  <strong>{archiveComparison.vixPercentile == null ? "—" : `${archiveComparison.vixPercentile.toFixed(0)}%`}</strong>
                  <p>Percentile rank within the current plus prior archived-session sample.</p>
                </article>
                <article>
                  <span>REGIME STREAK</span>
                  <strong>{archiveComparison.regimeStreak || "—"}</strong>
                  <p>Consecutive archived sessions with the same regime classification.</p>
                </article>
                <article>
                  <span>LEADERSHIP STREAK</span>
                  <strong>{archiveComparison.topSector ? archiveComparison.topSectorStreak : "—"}</strong>
                  <p>{archiveComparison.topSector ? `${archiveComparison.topSector} ranked first in ${archiveComparison.topSectorStreak} consecutive archived session${archiveComparison.topSectorStreak === 1 ? "" : "s"} and ${archiveComparison.topSectorLedCount} of the last ${archiveComparison.topSectorWindow}.` : "Sector ranking unavailable."}</p>
                </article>
                <article>
                  <span>S&amp;P 5-SESSION</span>
                  <strong className={toneClass(archiveComparison.sp500FiveSessionReturn)}>{formatPct(archiveComparison.sp500FiveSessionReturn)}</strong>
                  <p>{archiveComparison.sp500FiveSessionReturn == null ? "Needs five consecutive archived sessions." : "Compounded from five archived Daily Tape session returns."}</p>
                </article>
              </div>
            </section>
          )}

          {!archived && <WatchlistPanel assets={watchAssets} assetBaseHref={assetBaseHref} sessionLabel={editionShort} />}
        </Chapter>

        <Chapter
          id="leadership"
          number="02"
          title="Leadership & participation"
          dek="What is actually participating in the move?"
          contents={[
            ["sectors", "Sector leadership"],
            ...(hasRelativeStrength ? [["relative-strength", "Relative strength"] as [string, string]] : []),
            ["internals", "Market internals"],
          ]}
        >
          <section className="report-subsection" id="sectors" aria-labelledby="sectors-title">
            <SectionHeading id="sectors" chapter="Leadership" kicker="Sector leadership" title="Where the tape actually moved" share={shareFor("sectors", "Sector leadership")}>All 11 sector ETFs ranked by session return, with weighting and participation checks.</SectionHeading>
            <div className="comparison-strip" aria-label="Market breadth comparison">
              <div><span>CAP-WEIGHTED (SPY)</span><strong className={toneClass(breadth.spy_pct_change)}>{breadth.spy_pct_change == null ? "Unavailable" : formatPct(breadth.spy_pct_change)}</strong></div>
              <div><span>EQUAL-WEIGHT (RSP)</span><strong className={toneClass(breadth.rsp_pct_change)}>{breadth.rsp_pct_change == null ? "Unavailable" : formatPct(breadth.rsp_pct_change)}</strong></div>
              <div><span>ADVANCING / DECLINING</span><strong>{breadth.advances} / {breadth.declines}</strong></div>
              <div><span>POSITIVE SECTORS</span><strong>{breadth.positive_sector_share.toFixed(1)}%</strong></div>
            </div>
            {editorial && <p className="section-read">{editorial.sector_leadership.observed} <strong>Interpretation:</strong> {editorial.sector_leadership.interpretation}</p>}
            <div className="sector-board">
              {sectorEntries.map(([name, value], index) => {
                const symbol = sectorSymbol(name);
                const asset = symbol ? assetBySymbol[symbol] : undefined;
                return (
                  <div className="sector-row" key={name}>
                    <span className="rank">{String(index + 1).padStart(2, "0")}</span>
                    <span className="sector-name">{asset ? <a href={`${assetBaseHref}${asset.slug}/`}>{name}</a> : name}</span>
                    <div className="bar-track" aria-hidden="true"><span className={value >= 0 ? "bar-positive" : "bar-negative"} style={{ width: `${Math.max(5, (Math.abs(value) / sectorAbsMax) * 100)}%` }} /></div>
                    <strong className={toneClass(value)}>{formatPct(value)}</strong>
                  </div>
                );
              })}
            </div>
          </section>

          <div className={hasRelativeStrength ? "report-grid report-grid--split" : "report-grid"}>
            {hasRelativeStrength && (
              <section className="report-subsection" id="relative-strength" aria-labelledby="relative-strength-title">
                <SectionHeading id="relative-strength" chapter="Leadership" kicker="Relative strength" title="Who is actually outperforming?" share={shareFor("relative-strength", "Relative strength")}>Persistent leaders versus one-day winners, measured against SPY.</SectionHeading>
                <RelativeStrength rows={dailyReport.relative_strength?.rows} assetBaseHref={assetBaseHref} />
              </section>
            )}
            <section className="report-subsection internals-section" id="internals" aria-labelledby="internals-title">
              <SectionHeading id="internals" chapter="Leadership" kicker="Market internals" title="Is the move holding underneath?" share={shareFor("internals", "Market internals")}>
                Participation measured across stated, tracked universes. None of these is presented as NYSE or Nasdaq constituent breadth.
              </SectionHeading>
              <MarketInternals report={dailyReport} />
            </section>
          </div>
        </Chapter>

        <Chapter
          id="drivers"
          number="03"
          title="What drove the tape"
          dek="The verified context around the session, the read it supports, and the names that set the pace."
          contents={[["catalysts", "Verified catalysts"], ["interpretation", "Interpretation"], ["mega-cap", "Mega-cap & AI"]]}
        >
          <section className="report-subsection catalyst-section" id="catalysts" aria-labelledby="catalysts-title">
            <SectionHeading id="catalysts" chapter="Drivers" kicker="Verified catalysts" title="On the record" share={shareFor("catalysts", "Verified catalysts")}>
              Developments published between the prior close and this report, from official sources first and allowlisted publishers second. Listed as context, never as the cause of a move.
            </SectionHeading>
            <CatalystList catalysts={catalysts} assetBaseHref={assetBaseHref} />
          </section>

          <section className="thesis" id="interpretation" aria-labelledby="interpretation-title">
            <div className="thesis-label"><span id="interpretation-title">INTERPRETATION</span><span>BASED ON OBSERVED DATA</span></div>
            <blockquote>“{thesisQuote}”</blockquote>
            <p>{editorial?.regime.observed ?? capWeightMessage} Interpretation reflects price relationships; no event catalyst is inferred.</p>
          </section>

          <section className="report-subsection" id="mega-cap" aria-labelledby="mega-cap-title">
            <SectionHeading id="mega-cap" chapter="Drivers" kicker="Mega-cap & AI" title="The leadership engine" share={shareFor("mega-cap", "Mega-cap & AI")}>Close, session range, daily return, and the latest verified price path for the market’s most-watched technology names.</SectionHeading>
            {editorial && <p className="section-read">{editorial.megacap_leadership.observed} <strong>Interpretation:</strong> {editorial.megacap_leadership.interpretation}</p>}
            <div className="mega-grid">
              {megaCaps.map(({ ticker, name, item, chartValues, chartAxis: axis, chartSource }) => (
                <article className="mega-card" key={ticker}>
                  <div className="mega-head">
                    <div className="company-id">
                      {/* eslint-disable-next-line @next/next/no-img-element -- static export; decorative remote logo */}
                      <img loading="lazy" width={34} height={34} src={`https://s3-symbol-logo.tradingview.com/${megaCapLogoSlugs[ticker]}--big.svg`} alt="" />
                      <div><strong>{ticker}</strong><span>{name}</span></div>
                    </div>
                    <strong className={toneClass(item?.pct_change)}>{item ? formatPct(item.pct_change) : "UNAVAILABLE"}</strong>
                  </div>
                  <p>{decodeText(dailyReport.narrative.megacap_descriptions[ticker] ?? "")}</p>
                  <div className="mega-price">{item ? `$${formatNumber(item.end_price)}` : "—"}</div>
                  {item?.session_date && item.session_date !== dailyReport.session_date && <small className="local-session local-session--warn">Session {formatSessionDate(item.session_date, { month: "short", day: "numeric" })} · not the report session</small>}
                  <div className="mega-range">
                    <span>DAY LOW <b>{item?.day_low != null ? `$${formatNumber(item.day_low)}` : "—"}</b></span>
                    <span>DAY HIGH <b>{item?.day_high != null ? `$${formatNumber(item.day_high)}` : "—"}</b></span>
                    <a className="asset-card-link" href={`${assetBaseHref}${ticker.toLowerCase()}/`}>Open asset →</a>
                  </div>
                  <div className="mega-chart">
                    <div className="mega-chart-meta"><span>REGULAR SESSION</span><small>{chartSource === "intraday_5m" ? "5 MIN" : chartSource ? "OPEN / CLOSE" : "UNAVAILABLE"}</small></div>
                    <Sparkline values={chartValues} positive={(item?.pct_change ?? 0) >= 0} label={pathLabel(`${ticker} session`, chartValues)} />
                    <div className="mega-axis" aria-hidden="true">{axis.map((time, index) => <span key={`${ticker}-${time}-${index}`}>{time}</span>)}</div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </Chapter>

        <Chapter
          id="cross-asset"
          number="04"
          title="Cross-asset & macro"
          dek="Yields, oil, the dollar, credit, overseas closes and crypto: the read beyond U.S. equities."
          contents={[["macro", "Macro pulse"], ["rates", "Rates & credit"], ["global", "Global check"], ["digital", "Digital assets"]]}
        >
          <section className="report-subsection macro-grid" id="macro" aria-labelledby="macro-title">
            <div className="macro-copy">
              <p className="section-kicker"><span className="section-kicker__chapter">Macro</span><span>Macro pulse</span></p>
              <h3 id="macro-title">
                {tenYearChange == null ? "Yields unverified." : tenYearChange < 0 ? "Yields eased." : tenYearChange > 0 ? "Yields rose." : "Yields held."}<br />
                {!oil ? "Oil unverified." : oil.pct_change > 0 ? "Oil gained." : oil.pct_change < 0 ? "Oil fell." : "Oil held."}
              </h3>
              <p>{editorial ? <>{editorial.macro_read.observed} <strong>Interpretation:</strong> {editorial.macro_read.interpretation}</> : `The ten-year yield moved ${formatBpsFromPoints(tenYearChange)} to ${formatNumber(tenYear?.end_price)}%. DXY changed ${formatPct(dxy?.pct_change)}.`}</p>
              <div className="breadth-meter"><div className="meter-head"><span>POSITIVE SECTOR SHARE</span><strong>{breadth.positive_sector_share.toFixed(1)}%</strong></div><div className="meter-track" aria-hidden="true"><span style={{ width: `${breadth.positive_sector_share}%` }} /></div><small>Cap-weighted S&amp;P {breadth.spy_pct_change == null ? "unavailable" : formatPct(breadth.spy_pct_change)} vs. equal weight {breadth.rsp_pct_change == null ? "unavailable" : formatPct(breadth.rsp_pct_change)}</small></div>
              <SectionShare {...shareFor("macro", "Macro pulse")} />
            </div>
            <div className="chart-panel">
              <div className="chart-header"><span>S&amp;P 500 / REGULAR SESSION</span><strong>{formatNumber(sp?.end_price)}</strong></div>
              <PriceChart
                points={spPoints}
                name="S&P 500 regular session"
                format={{ digits: 2 }}
                stroke={(sp?.pct_change ?? 0) >= 0 ? "var(--up)" : "var(--down)"}
                size="panel"
              />
              <div className="chart-stats"><div><span>DAY LOW</span><strong>{formatNumber(sp?.day_low)}</strong></div><div><span>DAY HIGH</span><strong>{formatNumber(sp?.day_high)}</strong></div><div><span>NASDAQ 1D</span><strong className={toneClass(nasdaq?.pct_change)}>{formatPct(nasdaq?.pct_change)}</strong></div></div>
            </div>
          </section>

          <section className="report-subsection rates-section" id="rates" aria-labelledby="rates-title">
            <SectionHeading id="rates" chapter="Macro" kicker="Rates & credit" title="The cost-of-capital board" share={shareFor("rates", "Rates & credit")}>
              Session yields, the official Treasury curve, actual credit spreads and bond ETF proxies, each labeled with its source and date.
            </SectionHeading>
            <RatesCredit report={dailyReport} assetBaseHref={assetBaseHref} />
          </section>

          <section className="report-subsection global-section" id="global" aria-labelledby="global-title">
            <SectionHeading id="global" chapter="Macro" kicker="Global check" title="A split tape beyond Wall Street" share={shareFor("global", "Global check")}>Regional closes, daily direction, and each market’s latest verified path. Local closing times differ from New York.</SectionHeading>
            <div className="global-table" role="table" aria-label="Global market performance">
              <div className="global-row table-head" role="row"><span role="columnheader">MARKET</span><span role="columnheader">REGION</span><span role="columnheader">CLOSE</span><span role="columnheader">1D</span><span role="columnheader">PATH</span></div>
              {globalMarkets.map(([symbol, name, region]) => {
                const item = verified(market[symbol]);
                const chart = dailyReport.session_charts[symbol];
                const values = item && chart?.closes?.length && chart.closes.length >= 3 ? chart.closes : [];
                return (
                  <div className="global-row" role="row" key={symbol}>
                    <strong role="cell">{name}{item?.session_date && item.session_date !== dailyReport.session_date && <small className="local-session">Local close {formatSessionDate(item.session_date, { month: "short", day: "numeric" })}</small>}</strong><span role="cell">{region}</span>
                    <span role="cell">{item ? formatNumber(item.end_price) : "—"}</span>
                    <strong role="cell" className={toneClass(item?.pct_change)}>{item ? formatPct(item.pct_change) : "Unavailable"}</strong>
                    <div role="cell" className="global-spark"><Sparkline values={values} positive={(item?.pct_change ?? 0) >= 0} label={pathLabel(name, values)} /></div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="report-subsection digital-section" id="digital" aria-labelledby="digital-title">
            <SectionHeading id="digital" chapter="Macro" kicker="Digital assets" title="The liquidity read" share={shareFor("digital", "Digital assets")}>Crypto trades around the clock; each move is measured over the reported session.</SectionHeading>
            <div className="digital-grid">
              {cryptoMarkets.map(([symbol, name, ticker, narrativeKey]) => {
                const item = verified(market[symbol]);
                const chart = dailyReport.session_charts[symbol];
                const values = item && chart?.closes?.length && chart.closes.length >= 3 ? chart.closes : [];
                const asset = assetBySymbol[symbol];
                return (
                  <article className="digital-card" key={symbol}>
                    <div className="digital-head"><span>{ticker}</span><strong className={toneClass(item?.pct_change)}>{item ? formatPct(item.pct_change) : "UNAVAILABLE"}</strong></div>
                    <div className="digital-price">{item ? `$${formatNumber(item.end_price, item.end_price < 10 ? 4 : 0)}` : "—"}</div>
                    <span className="digital-name">{name}{item?.session_date && item.session_date !== dailyReport.session_date && <small className="local-session">UTC day {formatSessionDate(item.session_date, { month: "short", day: "numeric" })}</small>}</span>
                    {asset && <a className="asset-card-link" href={`${assetBaseHref}${asset.slug}/`}>Open asset →</a>}
                    <div className="digital-chart">
                      <div className="digital-chart-meta"><span>VERIFIED PATH</span><small>{chart?.source === "intraday_5m" ? "5 MIN" : chart?.source === "daily_5d_fallback" ? "5 DAY" : "UNAVAILABLE"}</small></div>
                      <Sparkline values={values} positive={(item?.pct_change ?? 0) >= 0} label={pathLabel(name, values, values[0] < 10 ? 4 : 0)} />
                    </div>
                    <p>{decodeText(dailyReport.narrative.crypto_descriptions[narrativeKey] ?? "")}</p>
                  </article>
                );
              })}
            </div>
          </section>
        </Chapter>

        <Chapter
          id="next-session"
          number="05"
          title="Next session"
          dek="What matters next: the decisions this close sets up, the scheduled events, and what could break the setup."
          contents={[["decision", "Decision summary"], ["calendar", "Market calendar"], ["ahead", "Forward look"]]}
          className="report-chapter--ahead"
        >
          <div className="report-grid report-grid--agenda">
            <section className="report-subsection decision-section" id="decision" aria-labelledby="decision-title">
              <SectionHeading id="decision" chapter="Ahead" kicker="Decision summary" title="Three decisions, not another essay" share={shareFor("decision", "Decision summary")}>The move, the cross-asset read, and the marker that matters next.</SectionHeading>
              <div className="decision-rows">{decisionSummary.map(([label, body], index) => <article key={label}><span>{String(index + 1).padStart(2, "0")}</span><strong>{label}</strong><p>{body}</p></article>)}</div>
            </section>
            <section className="report-subsection calendar-section" id="calendar" aria-labelledby="calendar-title">
              <SectionHeading id="calendar" chapter="Ahead" kicker="Market calendar" title="What’s on the tape" share={shareFor("calendar", "Market calendar")}>
                {archived ? "Scheduled events as recorded when this issue was published. " : ""}U.S. releases, Treasury auctions, tracked earnings and market-structure dates for this session and the next. Times in Central Time.
              </SectionHeading>
              <MarketCalendarList calendar={calendar} currentLabel="Report session" />
            </section>
          </div>

          <section className="report-subsection ahead" id="ahead" aria-labelledby="ahead-title">
            <SectionHeading id="ahead" chapter="Ahead" kicker="Forward look" title="What can break the setup" share={shareFor("ahead", "Forward look")}>Variables to monitor next, framed as conditions rather than predictions.</SectionHeading>
            {editorial && <ul className="ahead-watch">{editorial.watchlist.map((item) => <li key={item}>{item}</li>)}</ul>}
            <div className="ahead-grid">{outlookItems.map(([number, title, bullets]) => <details key={number}><summary><span>{number}</span><strong>{title}</strong><i aria-hidden="true">+</i></summary><ul>{bullets.slice(0, 2).map((bullet) => <li key={bullet}>{decodeText(bullet)}</li>)}</ul></details>)}</div>
          </section>
        </Chapter>

        <section className="report-endmatter" id="reference" aria-labelledby="reference-title">
          <div className="report-endmatter__head">
            <h2 id="reference-title">Reference &amp; methodology</h2>
            <p>Supporting reference levels, delivery options, and where every number on this page comes from.</p>
          </div>

          <div className="macro-reference" role="group" aria-label="Macro reference">
            <div><span>13W T-BILL</span><strong>{tBill ? `${formatNumber(tBill.end_price)}%` : "—"}</strong><small>{formatBpsFromPoints(tBill?.abs_change)}</small></div>
            <div><span>GOLD</span><strong>{gold ? `$${formatNumber(gold.end_price)}` : "—"}</strong><small className={toneClass(gold?.pct_change)}>{formatPct(gold?.pct_change)}</small></div>
            <div><span>WTI CRUDE</span><strong>{oil ? `$${formatNumber(oil.end_price)}` : "—"}</strong><small className={toneClass(oil?.pct_change)}>{formatPct(oil?.pct_change)}</small></div>
            <div><span>RUSSELL 2000</span><strong>{formatNumber(russell?.end_price)}</strong><small className={toneClass(russell?.pct_change)}>{formatPct(russell?.pct_change)}</small></div>
          </div>

          {!archived && <DeliveryPanel feedHref="./feed.xml" />}

          <aside className="method-note" id="data-health" aria-label="Data freshness, sources and methodology">
            <div><span>DATA FRESHNESS</span><strong>Through {formatSessionDate(dailyReport.session_date)} close</strong><small>Generated {generatedLabel}</small></div>
            <div className="method-note__body">
              <p>Daily figures compare the latest completed U.S. session with the immediately preceding trading-session close. “Breadth” is the share of the 11 S&amp;P sector ETFs that finished higher. Market data comes from Yahoo Finance via yfinance, with Stooq as a fallback for core indexes. Calendar and catalyst sources are listed separately below; unavailable feeds are shown, not filled in.</p>
              <FeedHealthList feeds={allFeeds} />
            </div>
            <div className={`quality-badge ${dataStatusLabel(quality).tone}`}>
              <span>DATA STATUS</span>
              <strong>{dataStatusLabel(quality).label.toUpperCase()}{quality ? ` · ${quality.coverage_pct.toFixed(1)}%` : ""}</strong>
              <small>{quality?.issues.length ? quality.issues.slice(0, 4).join("; ") : quality ? "No market-data issues flagged" : "Health metadata was not recorded for this issue"}</small>
            </div>
          </aside>
        </section>

        <footer>
          <div>
            <strong>THE DAILY TAPE</strong>
            <span>Signal over noise.</span>
            <nav className="footer-nav" aria-label="Footer">
              <a href={siteRoot}>Latest Close Tape</a>
              <a href={archiveHref}>All reports</a>
              <a href={searchHref}>Search</a>
              <a href="#top">Back to top ↑</a>
            </nav>
            <KeyboardShortcuts
              bindings={{
                "/": { kind: "href", href: searchHref, label: "Search assets and archive" },
                a: { kind: "href", href: archiveHref, label: "Report archive" },
                h: { kind: "anchor", id: "top", label: "Top of the report" },
                o: { kind: "anchor", id: "overview", label: "Market overview" },
                s: { kind: "anchor", id: "sectors", label: "Sector leadership" },
                m: { kind: "anchor", id: "macro", label: "Macro pulse" },
                c: { kind: "anchor", id: "calendar", label: "Market calendar" },
                ...(archived ? {} : { w: { kind: "anchor" as const, id: "watchlist", label: "Your watchlist" } }),
                ...(previousReportHref ? { ArrowLeft: { kind: "href" as const, href: previousReportHref, label: "Previous archived session" } } : {}),
                ...(nextReportHref ? { ArrowRight: { kind: "href" as const, href: nextReportHref, label: "Next archived session" } } : {}),
              }}
            />
          </div>
          <div className="footer-meta"><span>DATA: YAHOO FINANCE + LISTED SOURCES</span><span>FACT-BASED SUMMARY</span><span>REFRESHED {generatedLabel.toUpperCase()}</span></div>
        </footer>
      </div>
    </main>
  );
}
