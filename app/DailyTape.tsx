import ShareSummaryButton from "./components/ShareSummaryButton";
import DeliveryPanel from "./components/DeliveryPanel";
import WatchlistPanel, { type WatchAsset } from "./components/WatchlistPanel";
import { assetCatalog, assetBySymbol } from "./lib/assets";
import SiteHeader from "./components/SiteHeader";
import PublicationBanner from "./components/PublicationBanner";
import KeyboardShortcuts from "./components/KeyboardShortcuts";

type MarketDatum = {
  dates: string[];
  closes: number[];
  end_price: number;
  pct_change: number;
  abs_change: number;
  prev_close: number;
  session_open: number;
  day_high: number;
  day_low: number;
  session_date: string | null;
  previous_session_date: string | null;
  ticker_used: string;
  data_source?: string;
  source_symbol?: string;
  error: string | null;
};

type SessionChart = {
  times: string[];
  closes: number[];
  source: "intraday_5m" | "daily_ohlc_fallback" | "daily_5d_fallback";
  session_date: string;
  error: string | null;
};

type MegaCapSnapshot = {
  name: string;
  result: MarketDatum;
  session_chart?: SessionChart;
};

type EditorialReading = { observed: string; interpretation: string };
type EditorialBrief = {
  headline: string;
  opening_summary: string;
  regime: EditorialReading;
  sector_leadership: EditorialReading;
  megacap_leadership: EditorialReading;
  macro_read: EditorialReading;
  investor_takeaway: EditorialReading;
  watchlist: string[];
};

type MarketHeadline = {
  title: string;
  url: string;
  publisher: string;
  published_at: number | null;
  related_tickers: string[];
  affected_assets?: string[];
  category?: string;
};

type CalendarEvent = {
  date: string;
  time?: string;
  time_zone?: string | null;
  title?: string;
  ticker?: string;
  country?: string;
  category?: string;
  importance?: unknown;
  actual?: unknown;
  consensus?: unknown;
  previous?: unknown;
  source: string;
  source_url?: string;
};

type TrendParticipation = {
  above: number;
  valid: number;
  share_pct: number;
};

type AssetHistory = {
  symbol: string;
  dates: string[];
  closes: number[];
  returns: Record<string, number | null>;
  moving_averages: Record<string, number | null>;
  above_moving_average: Record<string, boolean | null>;
  source: string;
  as_of: string | null;
  error: string | null;
};

export type DailyReport = {
  report_type: "daily_market_close";
  session_date: string;
  previous_session_date: string;
  generated_at: string;
  report_mode: string;
  derived_metrics?: { risk_confirmation?: { signal: string } };
  data_quality?: {
    status: "healthy" | "degraded" | "limited";
    valid: number;
    total: number;
    coverage_pct: number;
    issues: string[];
    sources: Record<string, number>;
    checked_session: string;
  };
  market_headlines?: {
    items: MarketHeadline[];
    source: string;
    as_of: string | null;
    label: string;
    error: string | null;
  };
  market_calendar?: {
    economic: { items: CalendarEvent[]; source: string; as_of: string | null; error: string | null };
    earnings: { items: CalendarEvent[]; source: string; as_of: string | null; error: string | null };
    note: string;
  };
  rates_credit?: Record<string, MarketDatum | number | null>;
  market_internals?: {
    trend_participation: {
      above_20d: TrendParticipation | null;
      above_50d: TrendParticipation | null;
      above_200d: TrendParticipation | null;
      universe: string;
    };
    tracked_high_low?: {
      new_20d_highs: number;
      new_20d_lows: number;
      valid: number;
      universe: string;
    };
    sector_relative_strength_vs_spy: Record<string, Record<string, number | null>>;
    benchmark_returns: Record<string, number | null>;
    limitation: string;
  };
  asset_history?: Record<string, AssetHistory>;
  market_data: Record<string, MarketDatum>;
  session_charts: Record<string, SessionChart>;
  mega_cap_data?: Record<string, MegaCapSnapshot>;
  daily_sector_performance: Record<string, number>;
  daily_market_breadth: {
    advances: number;
    declines: number;
    positive_sector_share: number;
    spy_pct_change: number | null;
    rsp_pct_change: number | null;
  };
  narrative: {
    editorial?: EditorialBrief;
    megacap_descriptions: Record<string, string>;
    crypto_descriptions: Record<"btc" | "eth" | "sol" | "xrp", string>;
    daily_takeaway: { what_moved: string; why: string; what_to_watch: string };
    next_session_outlook: Record<"macro" | "fed_policy" | "earnings_and_catalysts" | "risk_factors", string[]>;
  };
};


const sections: Array<[string, string]> = [
  ["brief", "The brief"],
  ["scorecard", "Scorecard"],
  ["catalysts", "Catalysts"],
  ["sectors", "Sectors"],
  ["macro", "Macro"],
  ["ahead", "Ahead"],
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

function decodeText(value: string) {
  const named: Record<string, string> = {
    "&amp;": "&", "&quot;": "\"", "&apos;": "'", "&#x27;": "'",
    "&#39;": "'", "&lt;": "<", "&gt;": ">", "&nbsp;": " ",
  };
  let decoded = value;
  for (let pass = 0; pass < 3; pass += 1) {
    const next = decoded
      .replace(/&(amp|quot|apos|#x27|#39|lt|gt|nbsp);/g, (match) => named[match] ?? match)
      .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
      .replace(/&#(\d+);/g, (_, num) => String.fromCodePoint(Number(num)));
    if (next === decoded) break;
    decoded = next;
  }
  return decoded.replace(/<\/?strong>/g, "");
}

function formatNumber(value: number, digits = 2) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

function formatPct(value: number) {
  const normalized = Object.is(value, -0) ? 0 : value;
  return `${normalized >= 0 ? "+" : ""}${normalized.toFixed(2)}%`;
}

function formatBps(value: number) {
  const bps = Math.round(value * 100);
  return `${bps >= 0 ? "+" : ""}${bps} bps`;
}

function formatCalendarValue(value: unknown) {
  if (value == null || value === "") return "—";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "—";
  if (typeof value === "string") return value.trim() || "—";
  return "—";
}

function sectorLabel(value: string) {
  return value.replace(/\s*\([A-Z]+\)$/, "");
}

function splitHeadline(value: string) {
  const words = value.trim().split(/\s+/);
  if (words.length < 4) return { lead: value, accent: "" };

  const accentCount = Math.min(3, Math.max(2, Math.ceil(words.length / 2)));
  return {
    lead: words.slice(0, -accentCount).join(" "),
    accent: words.slice(-accentCount).join(" "),
  };
}

function isoWeek(value: Date) {
  const date = new Date(Date.UTC(value.getFullYear(), value.getMonth(), value.getDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil((((date.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
}

function hasVerifiedClose(item: MarketDatum | undefined) {
  return Boolean(item && !item.error && item.end_price > 0 && item.closes.length > 0);
}

function Sparkline({ values, positive }: { values: number[]; positive: boolean }) {
  if (values.length < 2) return <div className="spark-empty">No chart data</div>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = (index / (values.length - 1)) * 100;
    const y = 38 - ((value - min) / span) * 30;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg className="sparkline" viewBox="0 0 100 42" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} fill="none" stroke={positive ? "var(--up)" : "var(--down)"} strokeWidth="2.25" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function IndexCard({ item, chart, name, short, slug, assetBaseHref, currency = false, digits = 2, suffix = "" }: { item: MarketDatum; chart?: SessionChart; name: string; short: string; slug: string; assetBaseHref: string; currency?: boolean; digits?: number; suffix?: string }) {
  const positive = item.pct_change >= 0;
  return (
    <article className="index-card">
      <div className="card-topline">
        <span className="eyebrow">{short}</span>
        <span className={`move ${positive ? "positive" : "negative"}`}>{formatPct(item.pct_change)}</span>
      </div>
      <div className="index-value">{currency ? "$" : ""}{formatNumber(item.end_price, digits)}{suffix}</div>
      <div className="index-name">{name}</div>
      <a className="asset-card-link" href={`${assetBaseHref}${slug}/`}>Open asset →</a>
      <Sparkline values={chart?.closes ?? item.closes} positive={positive} />
    </article>
  );
}

function Signal({ label, value, note, tone }: { label: string; value: string; note: string; tone: "good" | "warn" | "neutral" }) {
  return (
    <div className="signal-row">
      <span className={`signal-dot ${tone}`} />
      <div><span className="signal-label">{label}</span><span className="signal-note">{note}</span></div>
      <strong>{value}</strong>
    </div>
  );
}

function parseMegaCapFallback(ticker: string, dailyReport: DailyReport): MarketDatum {
  const description = decodeText(dailyReport.narrative.megacap_descriptions[ticker] ?? "");
  const priceMatch = description.match(/\$([\d,]+(?:\.\d+)?)/);
  const moveMatch = description.match(/([+-]\d+(?:\.\d+)?)%/);
  const endPrice = Number((priceMatch?.[1] ?? "0").replace(/,/g, ""));
  const pctChange = Number(moveMatch?.[1] ?? 0);
  const prevClose = pctChange === -100 ? endPrice : endPrice / (1 + pctChange / 100);
  return {
    dates: [dailyReport.previous_session_date, dailyReport.session_date],
    closes: [prevClose, endPrice],
    end_price: endPrice,
    pct_change: pctChange,
    abs_change: endPrice - prevClose,
    prev_close: prevClose,
    session_open: prevClose,
    day_high: Math.max(prevClose, endPrice),
    day_low: Math.min(prevClose, endPrice),
    session_date: dailyReport.session_date,
    previous_session_date: dailyReport.previous_session_date,
    ticker_used: ticker,
    error: null,
  };
}

export default function DailyTape({
  report,
  archived = false,
  archiveHref = "./reports/",
  assetBaseHref = "./assets/",
  previousReportHref,
  nextReportHref,
  archiveComparison,
}: {
  report: DailyReport;
  archived?: boolean;
  archiveHref?: string;
  assetBaseHref?: string;
  previousReportHref?: string;
  nextReportHref?: string;
  archiveComparison?: {
    sampleSize: number;
    breadthAverage: number | null;
    breadthDelta: number | null;
    vixPercentile: number | null;
    regimeStreak: number;
    sp500FiveSessionReturn: number | null;
  };
}) {
  const dailyReport = report;
  const market = dailyReport.market_data;
  const siteRoot = archived ? "../../" : "./";
  const searchHref = `${siteRoot}search/`;
  const sectorEntries = Object.entries(dailyReport.daily_sector_performance).sort((a, b) => b[1] - a[1]);
  const sectorAbsMax = Math.max(...sectorEntries.map(([, value]) => Math.abs(value)));
  const topSector = sectorEntries[0];
  const bottomSector = sectorEntries[sectorEntries.length - 1];
  const megaCaps = Object.keys(megaCapNames).map((ticker) => {
    const snapshot = dailyReport.mega_cap_data?.[ticker];
    const item = snapshot?.result ?? parseMegaCapFallback(ticker, dailyReport);
    const chart = snapshot?.session_chart;
    const chartTimes = chart?.times?.length ? chart.times : ["9:30 AM", "4:00 PM"];
    return {
      ticker,
      name: snapshot?.name ?? megaCapNames[ticker],
      item,
      chartValues: chart?.closes?.length ? chart.closes : item.closes,
      chartAxis: [chartTimes[0], chartTimes[Math.floor(chartTimes.length / 2)], chartTimes.at(-1)].filter(Boolean) as string[],
      chartSource: chart?.source,
      hasSessionRange: Boolean(snapshot),
    };
  });
  const editorial = dailyReport.narrative.editorial;
  const headline = editorial?.headline ?? `${sectorLabel(topSector[0])} led the sector ranking.`;
  const headlineParts = splitHeadline(headline);
  const sp = market["^GSPC"];
  const nasdaq = market["^IXIC"];
  const russell = market["^RUT"];
  const vix = market["^VIX"];
  const tenYear = market["^TNX"];
  const tBill = market["^IRX"];
  const dxy = market["DX-Y.NYB"];
  const gold = market["GC=F"];
  const oil = market["CL=F"];
  const breadth = dailyReport.daily_market_breadth;
  const sessionDate = new Date(`${dailyReport.session_date}T12:00:00`);
  const previousSessionDate = new Date(`${dailyReport.previous_session_date}T12:00:00`);
  const dateRange = `${previousSessionDate.toLocaleDateString("en-US", { month: "short", day: "numeric" })} — ${sessionDate.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
  const issue = `${String(sessionDate.getFullYear()).slice(-2)}.${String(isoWeek(sessionDate)).padStart(2, "0")}`;
  const generatedAt = new Date(dailyReport.generated_at);
  const generatedLabel = generatedAt.toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" });
  const sectorTotal = sectorEntries.length;
  const breadthTone = breadth.positive_sector_share >= 60 ? "Broad" : breadth.positive_sector_share >= 45 ? "Mixed" : "Narrow";
  const riskSignal = dailyReport.derived_metrics?.risk_confirmation?.signal;
  const riskTone = riskSignal ? riskSignal === "risk_on_confirmed" ? "Constructive" : riskSignal === "risk_off_confirmed" ? "Defensive" : "Mixed"
    : sp.pct_change > 0 && vix.pct_change < 0 && breadth.positive_sector_share >= 60 ? "Constructive"
    : sp.pct_change < 0 && vix.pct_change > 0 && breadth.positive_sector_share <= 40 ? "Defensive" : "Mixed";
  const equalWeightGap = breadth.rsp_pct_change != null && breadth.spy_pct_change != null
    ? breadth.rsp_pct_change - breadth.spy_pct_change : null;
  const capWeightMessage = equalWeightGap === null
    ? "The equal-weight comparison is unavailable for this session."
    : equalWeightGap === 0 ? "Equal-weight and cap-weight returns matched."
    : `${equalWeightGap > 0 ? "Equal weight" : "Cap weight"} outperformed by ${Math.abs(equalWeightGap).toFixed(2)} percentage points. This is a participation proxy, not an attribution of index contributions.`;
  const thesisQuote = editorial?.regime.interpretation ?? capWeightMessage;
  const spChart = dailyReport.session_charts["^GSPC"];
  const chartTimes = spChart?.times ?? ["9:30 AM", "4:00 PM"];
  const chartAxis = [chartTimes[0], chartTimes[Math.floor(chartTimes.length / 2)], chartTimes.at(-1)].filter(Boolean) as string[];
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

  const watchAssets: WatchAsset[] = assetCatalog.map((asset) => {
    const direct = market[asset.symbol] ?? dailyReport.mega_cap_data?.[asset.symbol]?.result;
    const history = dailyReport.asset_history?.[asset.symbol];
    const sectorReturn = Object.entries(dailyReport.daily_sector_performance).find(([name]) => name.includes(`(${asset.symbol})`))?.[1];
    return {
      slug: asset.slug,
      symbol: asset.symbol,
      name: asset.name,
      price: direct?.end_price ?? history?.closes?.at(-1) ?? null,
      pct_change: direct?.pct_change ?? sectorReturn ?? history?.returns?.["5d"] ?? null,
    };
  }).filter((asset) => asset.price != null || asset.pct_change != null);

  const headlines = dailyReport.market_headlines?.items ?? [];
  const calendarEvents = [
    ...(dailyReport.market_calendar?.economic.items ?? []),
    ...(dailyReport.market_calendar?.earnings.items ?? []),
  ].sort((a, b) => `${a.date} ${a.time ?? ""}`.localeCompare(`${b.date} ${b.time ?? ""}`));

  const rateDatum = (key: string) => {
    const value = dailyReport.rates_credit?.[key];
    return value && typeof value === "object" && "end_price" in value ? value as MarketDatum : null;
  };
  const rateCards = [
    ["3M", rateDatum("3m"), "us-3m"],
    ["5Y", rateDatum("5y"), "us-5y"],
    ["10Y", rateDatum("10y") ?? tenYear, "us-10y"],
    ["30Y", rateDatum("30y"), "us-30y"],
    ["HYG", rateDatum("hyg"), "hyg"],
    ["LQD", rateDatum("lqd"), "lqd"],
    ["TIP", rateDatum("tip"), "tip"],
    ["MOVE", rateDatum("move"), "move"],
  ] as const;
  const curve5s10s = typeof dailyReport.rates_credit?.["5s10s_bp"] === "number"
    ? dailyReport.rates_credit["5s10s_bp"] as number
    : null;
  const internals = dailyReport.market_internals?.trend_participation;
  const dataQuality = dailyReport.data_quality;

  return (
    <main id="main">
      <SiteHeader root={siteRoot} current={archived ? "reports" : "close"} sectionLinks={sections} />
      <KeyboardShortcuts
        bindings={{
          "/": { kind: "href", href: searchHref },
          a: { kind: "href", href: archiveHref },
          m: { kind: "anchor", id: "macro" },
          s: { kind: "anchor", id: "scorecard" },
          w: { kind: "anchor", id: "watchlist" },
        }}
      />

      <div className="page" id="top">
        <section className="hero" id="brief">
          <div className="issue-line"><span>{archived ? "ARCHIVED DAILY TAPE" : "DAILY MARKET INTELLIGENCE"}</span><span><b>ISSUE</b> {issue}</span><span><b>SESSION</b> {dateRange.toUpperCase()}</span></div>
          {archived && (
            <div className="archive-session-nav" aria-label="Archived session navigation">
              <span>{previousReportHref ? <a href={previousReportHref}>← Previous session</a> : <i>Earliest archived session</i>}</span>
              <a href={archiveHref}>All reports</a>
              <span>{nextReportHref ? <a href={nextReportHref}>Next session →</a> : <i>Latest archived session</i>}</span>
            </div>
          )}
          {!archived && <PublicationBanner sessionDate={dailyReport.session_date} generatedAt={dailyReport.generated_at} />}
          <div className="hero-grid">
            <div className="hero-copy">
              <p className="section-kicker">THE ONE-LINE READ</p>
              <h1>
                {headlineParts.lead}
                {headlineParts.accent && <em>{headlineParts.accent}</em>}
              </h1>
              <p className="dek">{editorial?.opening_summary ?? dailyReport.narrative.daily_takeaway.what_moved}</p>
              <div className="hero-tags">
                <span className={`tag ${sp.pct_change >= 0 ? "up" : "down"}`}>S&amp;P {formatPct(sp.pct_change)}</span>
                <span className="tag neutral">Breadth {breadth.advances}/{sectorTotal}</span>
                <span className={`tag ${vix.pct_change <= 0 ? "up" : "down"}`}>VIX {formatPct(vix.pct_change)}</span>
                <ShareSummaryButton
                  headline={headline}
                  session={dateRange}
                  metrics={{
                    sp500: formatPct(sp.pct_change),
                    nasdaq: formatPct(nasdaq.pct_change),
                    vix: formatNumber(vix.end_price),
                    breadth: `${breadth.positive_sector_share.toFixed(1)}%`,
                  }}
                />
              </div>
            </div>
            <aside className="regime-card" aria-label="Market regime signals">
              <div className="regime-heading"><span>REGIME MONITOR</span><span className="live-dot">SESSION CLOSED</span></div>
              <Signal label="Risk appetite" value={riskTone} note={`S&P ${formatPct(sp.pct_change)} · VIX ${formatNumber(vix.end_price)}`} tone={riskTone === "Constructive" ? "good" : "warn"} />
              <Signal label="Participation" value={breadthTone} note={`${breadth.advances} of ${sectorTotal} sectors advanced`} tone={breadthTone === "Broad" ? "good" : "warn"} />
              <Signal label="Rates impulse" value={tenYear.abs_change <= 0 ? "Easing" : "Tightening"} note={`10Y ${formatNumber(tenYear.end_price)}% · ${formatBps(tenYear.abs_change)}`} tone={tenYear.abs_change <= 0 ? "good" : "warn"} />
              <Signal label="Dollar impulse" value={dxy.pct_change <= 0 ? "Easing" : "Firming"} note={`DXY ${formatNumber(dxy.end_price)} · ${formatPct(dxy.pct_change)}`} tone={dxy.pct_change <= 0 ? "good" : "warn"} />
            </aside>
          </div>
        </section>

        <section className="digest-strip" aria-label="Three-point market digest">
          <article><span>01 / MARKET</span><strong>{riskTone} close</strong><p>S&amp;P {formatPct(sp.pct_change)}; Nasdaq {formatPct(nasdaq.pct_change)}; VIX ended at {formatNumber(vix.end_price)}.</p></article>
          <article><span>02 / LEADERSHIP</span><strong>{sectorLabel(topSector[0])} over {sectorLabel(bottomSector[0])}</strong><p>A {Math.abs(topSector[1] - bottomSector[1]).toFixed(2)}-point spread separated the best and worst sectors.</p></article>
          <article><span>03 / INTERNALS</span><strong>{breadthTone} breadth</strong><p>{capWeightMessage}</p></article>
        </section>

        {archived && archiveComparison && archiveComparison.sampleSize > 0 && (
          <section className="archive-context section-block" aria-label="Historical session context">
            <div className="section-heading">
              <div><p className="section-kicker">HISTORICAL CONTEXT</p><h2>How this session compared</h2></div>
              <p>Context is calculated only from earlier archived Daily Tape sessions, so the comparison never uses future data.</p>
            </div>
            <div className="archive-context-grid">
              <article>
                <span>BREADTH VS PRIOR AVG</span>
                <strong>{archiveComparison.breadthDelta == null ? "—" : `${archiveComparison.breadthDelta >= 0 ? "+" : ""}${archiveComparison.breadthDelta.toFixed(1)} pp`}</strong>
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
                <p>Consecutive archived sessions with the same risk-confirmation regime.</p>
              </article>
              <article>
                <span>S&amp;P 5-SESSION</span>
                <strong className={(archiveComparison.sp500FiveSessionReturn ?? 0) >= 0 ? "positive" : "negative"}>
                  {archiveComparison.sp500FiveSessionReturn == null ? "—" : formatPct(archiveComparison.sp500FiveSessionReturn)}
                </strong>
                <p>Compounded from the archived Daily Tape session returns.</p>
              </article>
            </div>
          </section>
        )}

        <section className="scorecard section-block" id="scorecard">
          <div className="section-heading"><div><p className="section-kicker">01 / SCORECARD</p><h2>The tape, at a glance</h2></div><p>Previous close to latest close. Sparklines show the verified regular-hours session path when available.</p></div>
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

        <WatchlistPanel assets={watchAssets} assetBaseHref={assetBaseHref} />

        <section className="section-block catalyst-section" id="catalysts">
          <div className="section-heading">
            <div><p className="section-kicker">02 / CATALYSTS &amp; CALENDAR</p><h2>What the market is watching</h2></div>
            <p>Source-linked headlines and scheduled events are shown as context. They are not automatically treated as explanations for the tape.</p>
          </div>
          <div className="catalyst-grid">
            <div className="headline-list">
              <div className="subsection-head"><span>VERIFIED DEVELOPMENTS</span><small>{dailyReport.market_headlines?.source ?? "SOURCE FEED PENDING"}</small></div>
              {headlines.length ? headlines.slice(0, 6).map((item) => (
                <a href={item.url} target="_blank" rel="noreferrer" key={item.url}>
                  <div><span>{item.category ?? "Market news"} · {item.publisher}</span><small>{item.published_at ? new Date(item.published_at * 1000).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" }) : "TIME N/A"}</small></div>
                  <strong>{item.title}</strong>
                  {!!(item.affected_assets?.length ?? item.related_tickers.length) && <small>Affected assets: {(item.affected_assets?.length ? item.affected_assets : item.related_tickers).slice(0, 5).join(", ")}</small>}
                  <b>Source ↗</b>
                </a>
              )) : <div className="data-empty">No qualifying source-linked developments are stored in this snapshot. Low-quality or unverified publishers are omitted rather than filled with placeholders.</div>}
            </div>
            <div className="calendar-list">
              <div className="subsection-head"><span>MARKET CALENDAR</span><small>CENTRAL TIME WHEN SOURCE GMT IS AVAILABLE</small></div>
              {calendarEvents.length ? calendarEvents.slice(0, 8).map((event, index) => (
                <article key={`${event.date}-${event.title ?? event.ticker}-${index}`}>
                  <div><span>{new Date(`${event.date}T12:00:00`).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}</span><small>{event.time ?? "TBD"}{event.time_zone && event.time !== "TBD" && !event.time?.includes("CT") ? ` · ${event.time_zone}` : ""}</small></div>
                  <strong>{event.title ?? `${event.ticker} earnings`}</strong>
                  <p>{[event.category, event.country, event.source].filter(Boolean).join(" · ")}</p>
                  {(event.actual != null || event.consensus != null || event.previous != null) && (
                    <small>Actual {formatCalendarValue(event.actual)} · Consensus {formatCalendarValue(event.consensus)} · Previous {formatCalendarValue(event.previous)}</small>
                  )}
                  {event.source_url && <a href={event.source_url} target="_blank" rel="noreferrer">Source ↗</a>}
                </article>
              )) : <div className="data-empty">No calendar events are stored in this snapshot yet. Calendar availability is checked during report generation and failures remain visible instead of being guessed.</div>}
            </div>
          </div>
          <p className="data-disclaimer">{dailyReport.market_calendar?.note ?? "Scheduled events and headlines are context only; no causal market claim is inferred."}</p>
        </section>

        <section className="thesis section-block">
          <div className="thesis-label"><span>INTERPRETATION</span><span>3 MIN READ</span></div>
          <blockquote>“{thesisQuote}”</blockquote>
          <p>{editorial?.regime.observed ?? capWeightMessage} Interpretation reflects price relationships; no event catalyst is inferred.</p>
        </section>

        <section className="section-block" id="sectors">
          <div className="section-heading"><div><p className="section-kicker">02 / LEADERSHIP</p><h2>Where the tape actually moved</h2></div><p>All 11 sector ETFs ranked by session return, with breadth and weighting checks above.</p></div>
          <div className="comparison-strip" aria-label="Market breadth comparison">
            <div><span>CAP-WEIGHTED S&amp;P</span><strong className={(breadth.spy_pct_change ?? 0) >= 0 ? "positive" : "negative"}>{breadth.spy_pct_change == null ? "Unavailable" : formatPct(breadth.spy_pct_change)}</strong></div>
            <div><span>EQUAL-WEIGHT S&amp;P</span><strong className={(breadth.rsp_pct_change ?? 0) >= 0 ? "positive" : "negative"}>{breadth.rsp_pct_change == null ? "Unavailable" : formatPct(breadth.rsp_pct_change)}</strong></div>
            <div><span>SPY CHECK</span><strong className={(breadth.spy_pct_change ?? 0) >= 0 ? "positive" : "negative"}>{breadth.spy_pct_change == null ? "Unavailable" : formatPct(breadth.spy_pct_change)}</strong></div>
            <div><span>POSITIVE SECTORS</span><strong>{breadth.positive_sector_share.toFixed(1)}%</strong></div>
          </div>
          {editorial && <p>{editorial.sector_leadership.observed} <strong>Interpretation:</strong> {editorial.sector_leadership.interpretation}</p>}
          <div className="sector-board">
            {sectorEntries.map(([name, value], index) => (
              <div className="sector-row" key={name}>
                <span className="rank">{String(index + 1).padStart(2, "0")}</span><span className="sector-name">{(() => {
                  const symbol = name.match(/\(([A-Z]+)\)$/)?.[1];
                  const asset = symbol ? assetBySymbol[symbol] : undefined;
                  return asset ? <a href={`${assetBaseHref}${asset.slug}/`}>{name}</a> : name;
                })()}</span>
                <div className="bar-track"><span className={value >= 0 ? "bar-positive" : "bar-negative"} style={{ width: `${Math.max(5, (Math.abs(value) / sectorAbsMax) * 100)}%` }} /></div>
                <strong className={value >= 0 ? "positive" : "negative"}>{formatPct(value)}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="section-block internals-section" id="internals">
          <div className="section-heading">
            <div><p className="section-kicker">03 / MARKET INTERNALS</p><h2>Is the move holding underneath?</h2></div>
            <p>Trend participation uses the 11 sector ETFs as a transparent proxy. It is intentionally not labeled as NYSE or Nasdaq constituent breadth.</p>
          </div>
          <div className="internals-grid">
            {([
              ["ABOVE 20D", internals?.above_20d],
              ["ABOVE 50D", internals?.above_50d],
              ["ABOVE 200D", internals?.above_200d],
            ] as Array<[string, TrendParticipation | null | undefined]>).map(([label, metric]) => (
              <article key={label}>
                <span>{label}</span>
                <strong>{metric ? `${metric.share_pct.toFixed(1)}%` : "—"}</strong>
                <p>{metric ? `${metric.above} of ${metric.valid} sector ETFs above trend` : "Available after the next enriched report refresh."}</p>
              </article>
            ))}
            <article>
              <span>CAP VS EQUAL WEIGHT</span>
              <strong>{equalWeightGap == null ? "—" : `${equalWeightGap >= 0 ? "+" : ""}${equalWeightGap.toFixed(2)} pp`}</strong>
              <p>{equalWeightGap == null ? "Comparison unavailable." : equalWeightGap > 0 ? "Equal weight led cap weight." : equalWeightGap < 0 ? "Cap weight led equal weight." : "Equal and cap weighting matched."}</p>
            </article>
            <article>
              <span>NEW 20D HIGHS</span>
              <strong>{dailyReport.market_internals?.tracked_high_low ? dailyReport.market_internals.tracked_high_low.new_20d_highs : "—"}</strong>
              <p>{dailyReport.market_internals?.tracked_high_low ? `${dailyReport.market_internals.tracked_high_low.valid} tracked risk assets checked` : "Available after the next enriched report refresh."}</p>
            </article>
            <article>
              <span>NEW 20D LOWS</span>
              <strong>{dailyReport.market_internals?.tracked_high_low ? dailyReport.market_internals.tracked_high_low.new_20d_lows : "—"}</strong>
              <p>{dailyReport.market_internals?.tracked_high_low?.universe ?? "Transparent tracked-universe proxy, not exchange-wide breadth."}</p>
            </article>
          </div>
          {dailyReport.market_internals?.sector_relative_strength_vs_spy && (
            <div className="relative-strength">
              <div className="subsection-head"><span>SECTOR RELATIVE STRENGTH VS SPY</span><small>5D / 1M / 3M</small></div>
              {Object.entries(dailyReport.market_internals.sector_relative_strength_vs_spy)
                .sort((a, b) => (b[1]["1m"] ?? -999) - (a[1]["1m"] ?? -999))
                .map(([name, windows]) => {
                  const symbol = name.match(/\(([A-Z]+)\)$/)?.[1];
                  const asset = symbol ? assetBySymbol[symbol] : undefined;
                  return (
                    <div className="relative-row" key={name}>
                      <span>{asset ? <a href={`${assetBaseHref}${asset.slug}/`}>{sectorLabel(name)}</a> : sectorLabel(name)}</span>
                      <strong className={(windows["5d"] ?? 0) >= 0 ? "positive" : "negative"}>{formatPct(windows["5d"] ?? 0)}</strong>
                      <strong className={(windows["1m"] ?? 0) >= 0 ? "positive" : "negative"}>{formatPct(windows["1m"] ?? 0)}</strong>
                      <strong className={(windows["3m"] ?? 0) >= 0 ? "positive" : "negative"}>{formatPct(windows["3m"] ?? 0)}</strong>
                    </div>
                  );
                })}
            </div>
          )}
        </section>

        <section className="section-block" id="mega-cap">
          <div className="section-heading"><div><p className="section-kicker">03 / MEGA-CAP &amp; AI</p><h2>The leadership engine</h2></div><p>Close, session range, daily return, and the latest verified price path for the market’s most-watched technology names.</p></div>
          {editorial && <p>{editorial.megacap_leadership.observed} <strong>Interpretation:</strong> {editorial.megacap_leadership.interpretation}</p>}
          <div className="mega-grid">
            {megaCaps.map(({ ticker, name, item, chartValues, chartAxis, chartSource, hasSessionRange }) => {
              const positive = item.pct_change >= 0;
              return (
                <article className="mega-card" key={ticker}>
                  <div className="mega-head">
                    <div className="company-id">
                      {/* eslint-disable-next-line @next/next/no-img-element -- static export; decorative remote logo */}
                      <img loading="lazy" width={34} height={34} src={`https://s3-symbol-logo.tradingview.com/${megaCapLogoSlugs[ticker]}--big.svg`} alt="" /><div><strong>{ticker}</strong><span>{name}</span></div></div>
                    <strong className={positive ? "positive" : "negative"}>{formatPct(item.pct_change)}</strong>
                  </div>
                  <p>{decodeText(dailyReport.narrative.megacap_descriptions[ticker] ?? "")}</p>
                  <div className="mega-price">${formatNumber(item.end_price)}</div>
                  <a className="asset-card-link" href={`${assetBaseHref}${ticker.toLowerCase()}/`}>Open asset →</a>
                  <div className="mega-range">
                    <span>{hasSessionRange ? "DAY LOW" : "PREV CLOSE"} <b>${formatNumber(hasSessionRange ? item.day_low : item.prev_close)}</b></span>
                    <span>{hasSessionRange ? "DAY HIGH" : "SESSION CLOSE"} <b>${formatNumber(hasSessionRange ? item.day_high : item.end_price)}</b></span>
                  </div>
                  <div className="mega-chart">
                    <div className="mega-chart-meta"><span>REGULAR SESSION</span><small>{chartSource === "intraday_5m" ? "5 MIN" : "OPEN / CLOSE"}</small></div>
                    <Sparkline values={chartValues} positive={positive} />
                    <div className="mega-axis">{chartAxis.map((time, index) => <span key={`${ticker}-${time}-${index}`}>{time}</span>)}</div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="macro-grid section-block" id="macro">
          <div className="macro-copy">
            <p className="section-kicker">04 / MACRO PULSE</p>
            <h2>Yields {tenYear.abs_change <= 0 ? "eased" : "rose"}.<br />Oil {oil.pct_change >= 0 ? "gained" : "fell"}.</h2>
            <p>{editorial ? <>{editorial.macro_read.observed} <strong>Interpretation:</strong> {editorial.macro_read.interpretation}</> : `The ten-year yield moved ${formatBps(tenYear.abs_change)} to ${formatNumber(tenYear.end_price)}%. DXY changed ${formatPct(dxy.pct_change)}.`}</p>
            <div className="breadth-meter"><div className="meter-head"><span>POSITIVE SECTOR SHARE</span><strong>{breadth.positive_sector_share.toFixed(1)}%</strong></div><div className="meter-track"><span style={{ width: `${breadth.positive_sector_share}%` }} /></div><small>Cap-weighted S&amp;P {breadth.spy_pct_change == null ? "Unavailable" : formatPct(breadth.spy_pct_change)} vs. equal weight {breadth.rsp_pct_change == null ? "Unavailable" : formatPct(breadth.rsp_pct_change)}</small></div>
          </div>
          <div className="chart-panel">
            <div className="chart-header"><span>S&amp;P 500 / REGULAR SESSION</span><strong>{formatNumber(sp.end_price)}</strong></div>
            <Sparkline values={spChart?.closes ?? sp.closes} positive={sp.pct_change >= 0} />
            <div className="chart-axis">{chartAxis.map((time, index) => <span key={`${time}-${index}`}>{time}</span>)}</div>
            <div className="chart-stats"><div><span>DAY LOW</span><strong>{formatNumber(sp.day_low)}</strong></div><div><span>DAY HIGH</span><strong>{formatNumber(sp.day_high)}</strong></div><div><span>NASDAQ 1D</span><strong className={nasdaq.pct_change >= 0 ? "positive" : "negative"}>{formatPct(nasdaq.pct_change)}</strong></div></div>
          </div>
        </section>

        <section className="section-block rates-section" id="rates">
          <div className="section-heading">
            <div><p className="section-kicker">05 / RATES &amp; CREDIT</p><h2>The cost-of-capital board</h2></div>
            <p>Treasury tenors plus high-yield, investment-grade, and inflation-protected bond proxies give the equity tape a broader fixed-income frame.</p>
          </div>
          <div className="rates-grid">
            {rateCards.map(([label, item, slug]) => (
              <a href={`${assetBaseHref}${slug}/`} key={label}>
                <span>{label}</span>
                <strong>{item ? `${formatNumber(item.end_price)}${label.endsWith("Y") || label === "3M" ? "%" : ""}` : "—"}</strong>
                <b className={item ? (item.pct_change >= 0 ? "positive" : "negative") : "muted"}>{item ? formatPct(item.pct_change) : "PENDING"}</b>
              </a>
            ))}
            <article>
              <span>5s10s CURVE</span>
              <strong>{curve5s10s == null ? "—" : `${curve5s10s >= 0 ? "+" : ""}${curve5s10s.toFixed(1)} bps`}</strong>
              <b className="muted">5Y → 10Y</b>
            </article>
          </div>
        </section>

        <section className="section-block decision-section">
          <div className="section-heading"><div><p className="section-kicker">05 / DECISION SUMMARY</p><h2>Three decisions, not another essay</h2></div><p>The move, the cross-asset explanation, and the marker that matters next.</p></div>
          <div className="decision-rows">{decisionSummary.map(([label, body], index) => <article key={label}><span>{String(index + 1).padStart(2, "0")}</span><strong>{label}</strong><p>{body}</p></article>)}</div>
        </section>

        <section className="section-block global-section">
          <div className="section-heading"><div><p className="section-kicker">06 / GLOBAL CHECK</p><h2>A split tape beyond Wall Street</h2></div><p>Regional closes, daily direction, and each market’s latest verified path.</p></div>
          <div className="global-table" role="table" aria-label="Global market performance">
            <div className="global-row table-head" role="row"><span>MARKET</span><span>REGION</span><span>CLOSE</span><span>1D</span><span>PATH</span></div>
            {globalMarkets.filter(([symbol]) => hasVerifiedClose(market[symbol])).map(([symbol, name, region]) => {
              const item = market[symbol];
              const chart = dailyReport.session_charts[symbol];
              const chartValues = chart?.closes?.length && chart.closes.length >= 3 ? chart.closes : [];
              return <div className="global-row" role="row" key={symbol}><strong>{name}</strong><span>{region}</span><span>{formatNumber(item.end_price)}</span><strong className={item.pct_change >= 0 ? "positive" : "negative"}>{formatPct(item.pct_change)}</strong><div className="global-spark"><Sparkline values={chartValues} positive={item.pct_change >= 0} /></div></div>;
            })}
          </div>
        </section>

        <section className="section-block digital-section">
          <div className="section-heading"><div><p className="section-kicker">07 / DIGITAL ASSETS</p><h2>The liquidity read</h2></div><p>Compact crypto cards use the same price, change, and verified-path language as Mega-Cap &amp; AI.</p></div>
          <div className="digital-grid">
            {cryptoMarkets.map(([symbol, name, ticker, narrativeKey]) => {
              const item = market[symbol];
              const chart = dailyReport.session_charts[symbol];
              const chartValues = chart?.closes?.length && chart.closes.length >= 3 ? chart.closes : [];
              const positive = item.pct_change >= 0;
              const asset = assetBySymbol[symbol];
              return <article className="digital-card" key={symbol}><div className="digital-head"><span>{ticker}</span><strong className={positive ? "positive" : "negative"}>{formatPct(item.pct_change)}</strong></div><div className="digital-price">${formatNumber(item.end_price, item.end_price < 10 ? 4 : 0)}</div><span className="digital-name">{name}</span>{asset && <a className="asset-card-link" href={`${assetBaseHref}${asset.slug}/`}>Open asset →</a>}<div className="digital-chart"><div className="digital-chart-meta"><span>VERIFIED PATH</span><small>{chart?.source === "intraday_5m" ? "5 MIN" : chart?.source === "daily_5d_fallback" ? "5 DAY" : "UNAVAILABLE"}</small></div><Sparkline values={chartValues} positive={positive} /></div><p>{decodeText(dailyReport.narrative.crypto_descriptions[narrativeKey])}</p></article>;
            })}
          </div>
        </section>

        <section className="section-block ahead" id="ahead">
          <div className="section-heading"><div><p className="section-kicker">08 / FORWARD LOOK</p><h2>What can break the setup</h2></div><p>Four variables to monitor next—framed as scenarios, not scheduled-event claims.</p></div>
          {editorial && <ul>{editorial.watchlist.map((item) => <li key={item}>{item}</li>)}</ul>}
          <div className="ahead-grid">{outlookItems.map(([number, title, bullets]) => <details key={number}><summary><span>{number}</span><strong>{title}</strong><i>+</i></summary><ul>{bullets.slice(0, 2).map((bullet) => <li key={bullet}>{decodeText(bullet)}</li>)}</ul></details>)}</div>
        </section>

        <section className="macro-reference" aria-label="Macro Reference">
          <div><span>13W T-BILL</span><strong>{formatNumber(tBill.end_price)}%</strong><small>{formatBps(tBill.abs_change)}</small></div>
          <div><span>GOLD</span><strong>${formatNumber(gold.end_price)}</strong><small className={gold.pct_change >= 0 ? "positive" : "negative"}>{formatPct(gold.pct_change)}</small></div>
          <div><span>WTI CRUDE</span><strong>${formatNumber(oil.end_price)}</strong><small className={oil.pct_change >= 0 ? "positive" : "negative"}>{formatPct(oil.pct_change)}</small></div>
          <div><span>RUSSELL 2000</span><strong>{formatNumber(russell.end_price)}</strong><small className={russell.pct_change >= 0 ? "positive" : "negative"}>{formatPct(russell.pct_change)}</small></div>
        </section>

        {!archived && <DeliveryPanel feedHref="./feed.xml" />}

        <aside className="method-note" aria-label="Data freshness and methodology">
          <div><span>DATA FRESHNESS</span><strong>Through {sessionDate.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })} close</strong></div>
          <p>Daily figures compare the latest completed U.S. session with the immediately preceding trading-session close. “Breadth” is the share of the 11 S&amp;P sector ETFs that finished higher. Headlines and calendars are displayed as sourced context, never silently converted into causal claims.</p>
          <div className={`quality-badge ${dataQuality?.status ?? "legacy"}`}>
            <span>DATA HEALTH</span>
            <strong>{dataQuality ? `${dataQuality.status.toUpperCase()} · ${dataQuality.coverage_pct.toFixed(1)}%` : "LEGACY SNAPSHOT"}</strong>
            <small>{dataQuality?.issues.length ? `${dataQuality.issues.length} issue${dataQuality.issues.length === 1 ? "" : "s"} flagged` : dataQuality ? "No critical issues flagged" : "Health metadata begins with the next report"}</small>
          </div>
        </aside>

        <footer><div><strong>THE DAILY TAPE</strong><span>Signal over noise.</span><a href={archiveHref}>Report archive</a><small className="shortcut-hint">SHORTCUTS · / SEARCH · A ARCHIVE · S SCORECARD · M MACRO · W WATCHLIST</small></div><div className="footer-meta"><span>DATA: YAHOO FINANCE + FALLBACKS</span><span>FACT-BASED SUMMARY</span><span>REFRESHED {generatedLabel.toUpperCase()}</span></div></footer>
      </div>
    </main>
  );
}
