"use client";

import { useEffect, useMemo, useState } from "react";
import report from "../report_snapshot.json";

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
  error: string | null;
};

type SessionChart = {
  times: string[];
  closes: number[];
  source: "intraday_5m" | "daily_ohlc_fallback";
  session_date: string;
  error: string | null;
};

type MegaCapSnapshot = {
  name: string;
  result: MarketDatum;
};

type DailyReport = {
  report_type: "daily_market_close";
  session_date: string;
  previous_session_date: string;
  generated_at: string;
  report_mode: string;
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
    megacap_descriptions: Record<string, string>;
    crypto_descriptions: Record<"btc" | "eth" | "sol" | "xrp", string>;
    daily_takeaway: { what_moved: string; why: string; what_to_watch: string };
    next_session_outlook: Record<"macro" | "fed_policy" | "earnings_and_catalysts" | "risk_factors", string[]>;
  };
};

const dailyReport = report as unknown as DailyReport;
const market = dailyReport.market_data;

const sections = [
  ["brief", "The brief"],
  ["scorecard", "Scorecard"],
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

function sectorLabel(value: string) {
  return value.replace(/\s*\([A-Z]+\)$/, "");
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

function IndexCard({ symbol, name, short, currency = false, digits = 2, suffix = "" }: { symbol: string; name: string; short: string; currency?: boolean; digits?: number; suffix?: string }) {
  const item = market[symbol];
  const chart = dailyReport.session_charts[symbol];
  const positive = item.pct_change >= 0;
  return (
    <article className="index-card">
      <div className="card-topline">
        <span className="eyebrow">{short}</span>
        <span className={`move ${positive ? "positive" : "negative"}`}>{formatPct(item.pct_change)}</span>
      </div>
      <div className="index-value">{currency ? "$" : ""}{formatNumber(item.end_price, digits)}{suffix}</div>
      <div className="index-name">{name}</div>
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

function parseMegaCapFallback(ticker: string): MarketDatum {
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

export default function Home() {
  const [theme, setTheme] = useState<"paper" | "ink">("paper");

  useEffect(() => {
    const saved = window.localStorage.getItem("daily-tape-theme");
    if (saved === "ink") setTheme("ink");
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("daily-tape-theme", theme);
  }, [theme]);

  const sectorEntries = useMemo(
    () => Object.entries(dailyReport.daily_sector_performance).sort((a, b) => b[1] - a[1]),
    [],
  );
  const sectorAbsMax = Math.max(...sectorEntries.map(([, value]) => Math.abs(value)));
  const topSector = sectorEntries[0];
  const bottomSector = sectorEntries[sectorEntries.length - 1];
  const megaCaps = useMemo(() => Object.keys(megaCapNames).map((ticker) => ({
    ticker,
    name: dailyReport.mega_cap_data?.[ticker]?.name ?? megaCapNames[ticker],
    item: dailyReport.mega_cap_data?.[ticker]?.result ?? parseMegaCapFallback(ticker),
    hasSessionRange: Boolean(dailyReport.mega_cap_data?.[ticker]),
  })), []);
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
  const sectorTotal = breadth.advances + breadth.declines;
  const breadthTone = breadth.positive_sector_share >= 60 ? "Broad" : breadth.positive_sector_share >= 45 ? "Mixed" : "Narrow";
  const riskTone = sp.pct_change >= 0 && vix.pct_change <= 0 ? "Constructive" : sp.pct_change < 0 && vix.pct_change > 0 ? "Defensive" : "Mixed";
  const equalWeightGap = (breadth.rsp_pct_change ?? 0) - (breadth.spy_pct_change ?? 0);
  const capWeightMessage = equalWeightGap > 0
    ? `Equal weight beat cap weight by ${Math.abs(equalWeightGap).toFixed(2)} points, showing that participation reached beyond the largest stocks.`
    : `Cap weight beat equal weight by ${Math.abs(equalWeightGap).toFixed(2)} points, showing that the largest stocks carried the index.`;
  const thesisQuote = equalWeightGap > 0 ? "The average stock outran the headline index." : "The headline index outran the average stock.";
  const spChart = dailyReport.session_charts["^GSPC"];
  const chartTimes = spChart?.times ?? ["9:30 AM", "4:00 PM"];
  const chartAxis = [chartTimes[0], chartTimes[Math.floor(chartTimes.length / 2)], chartTimes.at(-1)].filter(Boolean) as string[];
  const decisionSummary = [
    ["What moved", `S&P 500 ${formatPct(sp.pct_change)} and Nasdaq ${formatPct(nasdaq.pct_change)} for the session; ${sectorLabel(topSector[0])} led while ${sectorLabel(bottomSector[0])} lagged.`],
    ["Why", `Leadership rotated from ${sectorLabel(bottomSector[0])} (${formatPct(bottomSector[1])}) toward ${sectorLabel(topSector[0])} (${formatPct(topSector[1])}); WTI moved ${formatPct(oil.pct_change)}.`],
    ["What to watch", decodeText(dailyReport.narrative.daily_takeaway.what_to_watch)],
  ];
  const outlookItems: Array<[string, string, string[]]> = [
    ["01", "Macro data", dailyReport.narrative.next_session_outlook.macro],
    ["02", "Fed & rates", dailyReport.narrative.next_session_outlook.fed_policy],
    ["03", "Earnings & AI", dailyReport.narrative.next_session_outlook.earnings_and_catalysts],
    ["04", "Risk dashboard", dailyReport.narrative.next_session_outlook.risk_factors],
  ];

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="The Daily Tape home"><span className="brand-mark"><i /><i /><i /></span><span>THE DAILY TAPE</span></a>
        <nav aria-label="Report sections">{sections.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}</nav>
        <button className="theme-toggle" onClick={() => setTheme((current) => current === "paper" ? "ink" : "paper")} aria-label={`Switch to ${theme === "paper" ? "dark" : "light"} theme`}>
          <span>{theme === "paper" ? "◐" : "◑"}</span>{theme === "paper" ? "Ink" : "Paper"}
        </button>
      </header>

      <div className="page" id="top">
        <section className="hero" id="brief">
          <div className="issue-line"><span>DAILY MARKET INTELLIGENCE</span><span>ISSUE {issue}</span><span>{dateRange.toUpperCase()}</span></div>
          <div className="hero-grid">
            <div className="hero-copy">
              <p className="section-kicker">THE ONE-LINE READ</p>
              <h1>{sectorLabel(topSector[0])} held up.<br /><em>{sectorLabel(bottomSector[0])} gave way.</em></h1>
              <p className="dek">The S&amp;P 500 ended {formatPct(sp.pct_change)} and the Nasdaq {formatPct(nasdaq.pct_change)}. {sectorLabel(topSector[0])} led at {formatPct(topSector[1])}, {sectorLabel(bottomSector[0])} lagged at {formatPct(bottomSector[1])}, and volatility finished {vix.pct_change >= 0 ? "higher" : "lower"}.</p>
              <div className="hero-tags">
                <span className={`tag ${sp.pct_change >= 0 ? "up" : "down"}`}>S&amp;P {formatPct(sp.pct_change)}</span>
                <span className="tag neutral">Breadth {breadth.advances}/{sectorTotal}</span>
                <span className={`tag ${vix.pct_change <= 0 ? "up" : "down"}`}>VIX {formatPct(vix.pct_change)}</span>
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

        <section className="scorecard section-block" id="scorecard">
          <div className="section-heading"><div><p className="section-kicker">01 / SCORECARD</p><h2>The tape, at a glance</h2></div><p>Previous close to latest close. Sparklines show the verified regular-hours session path when available.</p></div>
          <div className="index-grid">
            <IndexCard symbol="^GSPC" name="S&P 500" short="SPX" />
            <IndexCard symbol="^IXIC" name="Nasdaq Composite" short="COMP" />
            <IndexCard symbol="^DJI" name="Dow Jones" short="DJIA" />
            <IndexCard symbol="^VIX" name="CBOE Volatility" short="VIX" />
            <IndexCard symbol="^TNX" name="10-Year Treasury" short="10Y" suffix="%" />
            <IndexCard symbol="DX-Y.NYB" name="U.S. Dollar Index" short="DXY" />
            <IndexCard symbol="BTC-USD" name="Bitcoin" short="BTC" currency digits={0} />
            <IndexCard symbol="ETH-USD" name="Ethereum" short="ETH" currency digits={0} />
          </div>
        </section>

        <section className="thesis section-block">
          <div className="thesis-label"><span>THE HOUSE VIEW</span><span>3 MIN READ</span></div>
          <blockquote>“{thesisQuote}”</blockquote>
          <p>{capWeightMessage} {sectorLabel(topSector[0])}, {sectorLabel(sectorEntries[1][0])}, and {sectorLabel(sectorEntries[2][0])} led, while the VIX moved {formatPct(vix.pct_change)} to {formatNumber(vix.end_price)}.</p>
        </section>

        <section className="section-block" id="sectors">
          <div className="section-heading"><div><p className="section-kicker">02 / LEADERSHIP</p><h2>Where the tape actually moved</h2></div><p>All 11 sector ETFs ranked by session return, with breadth and weighting checks above.</p></div>
          <div className="comparison-strip" aria-label="Market breadth comparison">
            <div><span>CAP-WEIGHTED S&amp;P</span><strong className={(breadth.spy_pct_change ?? 0) >= 0 ? "positive" : "negative"}>{formatPct(breadth.spy_pct_change ?? 0)}</strong></div>
            <div><span>EQUAL-WEIGHT S&amp;P</span><strong className={(breadth.rsp_pct_change ?? 0) >= 0 ? "positive" : "negative"}>{formatPct(breadth.rsp_pct_change ?? 0)}</strong></div>
            <div><span>SPY CHECK</span><strong className={(breadth.spy_pct_change ?? 0) >= 0 ? "positive" : "negative"}>{formatPct(breadth.spy_pct_change ?? 0)}</strong></div>
            <div><span>POSITIVE SECTORS</span><strong>{breadth.positive_sector_share.toFixed(1)}%</strong></div>
          </div>
          <div className="sector-board">
            {sectorEntries.map(([name, value], index) => (
              <div className="sector-row" key={name}>
                <span className="rank">{String(index + 1).padStart(2, "0")}</span><span className="sector-name">{name}</span>
                <div className="bar-track"><span className={value >= 0 ? "bar-positive" : "bar-negative"} style={{ width: `${Math.max(5, (Math.abs(value) / sectorAbsMax) * 100)}%` }} /></div>
                <strong className={value >= 0 ? "positive" : "negative"}>{formatPct(value)}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="section-block" id="mega-cap">
          <div className="section-heading"><div><p className="section-kicker">03 / MEGA-CAP &amp; AI</p><h2>The leadership engine</h2></div><p>Close, session range, daily return, and the latest verified price path for the market’s most-watched technology names.</p></div>
          <div className="mega-grid">
            {megaCaps.map(({ ticker, name, item, hasSessionRange }) => {
              const positive = item.pct_change >= 0;
              return (
                <article className="mega-card" key={ticker}>
                  <div className="mega-head">
                    <div className="company-id"><img src={`https://s3-symbol-logo.tradingview.com/${megaCapLogoSlugs[ticker]}--big.svg`} alt="" /><div><strong>{ticker}</strong><span>{name}</span></div></div>
                    <strong className={positive ? "positive" : "negative"}>{formatPct(item.pct_change)}</strong>
                  </div>
                  <div className="mega-price">${formatNumber(item.end_price)}</div>
                  <div className="mega-range">
                    <span>{hasSessionRange ? "DAY LOW" : "PREV CLOSE"} <b>${formatNumber(hasSessionRange ? item.day_low : item.prev_close)}</b></span>
                    <span>{hasSessionRange ? "DAY HIGH" : "SESSION CLOSE"} <b>${formatNumber(hasSessionRange ? item.day_high : item.end_price)}</b></span>
                  </div>
                  <Sparkline values={item.closes} positive={positive} />
                </article>
              );
            })}
          </div>
        </section>

        <section className="macro-grid section-block" id="macro">
          <div className="macro-copy">
            <p className="section-kicker">04 / MACRO PULSE</p>
            <h2>Yields {tenYear.abs_change <= 0 ? "eased" : "rose"}.<br />Oil {oil.pct_change >= 0 ? "gained" : "fell"}.</h2>
            <p>The 10-year yield moved {formatBps(tenYear.abs_change)} to {formatNumber(tenYear.end_price)}%, while WTI moved {formatPct(oil.pct_change)} to ${formatNumber(oil.end_price)}. The dollar changed {formatPct(dxy.pct_change)}, keeping the cross-asset message mixed.</p>
            <div className="breadth-meter"><div className="meter-head"><span>POSITIVE SECTOR SHARE</span><strong>{breadth.positive_sector_share.toFixed(1)}%</strong></div><div className="meter-track"><span style={{ width: `${breadth.positive_sector_share}%` }} /></div><small>Cap-weighted S&amp;P {formatPct(breadth.spy_pct_change ?? 0)} vs. equal weight {formatPct(breadth.rsp_pct_change ?? 0)}</small></div>
          </div>
          <div className="chart-panel">
            <div className="chart-header"><span>S&amp;P 500 / REGULAR SESSION</span><strong>{formatNumber(sp.end_price)}</strong></div>
            <Sparkline values={spChart?.closes ?? sp.closes} positive={sp.pct_change >= 0} />
            <div className="chart-axis">{chartAxis.map((time, index) => <span key={`${time}-${index}`}>{time}</span>)}</div>
            <div className="chart-stats"><div><span>DAY LOW</span><strong>{formatNumber(sp.day_low)}</strong></div><div><span>DAY HIGH</span><strong>{formatNumber(sp.day_high)}</strong></div><div><span>NASDAQ 1D</span><strong className={nasdaq.pct_change >= 0 ? "positive" : "negative"}>{formatPct(nasdaq.pct_change)}</strong></div></div>
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
              return <div className="global-row" role="row" key={symbol}><strong>{name}</strong><span>{region}</span><span>{formatNumber(item.end_price)}</span><strong className={item.pct_change >= 0 ? "positive" : "negative"}>{formatPct(item.pct_change)}</strong><div className="global-spark"><Sparkline values={item.closes} positive={item.pct_change >= 0} /></div></div>;
            })}
          </div>
        </section>

        <section className="section-block digital-section">
          <div className="section-heading"><div><p className="section-kicker">07 / DIGITAL ASSETS</p><h2>The liquidity read</h2></div><p>Compact crypto cards use the same price, change, and verified-path language as Mega-Cap &amp; AI.</p></div>
          <div className="digital-grid">
            {cryptoMarkets.map(([symbol, name, ticker, narrativeKey]) => {
              const item = market[symbol];
              const positive = item.pct_change >= 0;
              return <article className="digital-card" key={symbol}><div className="digital-head"><span>{ticker}</span><strong className={positive ? "positive" : "negative"}>{formatPct(item.pct_change)}</strong></div><div className="digital-price">${formatNumber(item.end_price, item.end_price < 10 ? 4 : 0)}</div><span className="digital-name">{name}</span><Sparkline values={item.closes} positive={positive} /><p>{decodeText(dailyReport.narrative.crypto_descriptions[narrativeKey])}</p></article>;
            })}
          </div>
        </section>

        <section className="section-block ahead" id="ahead">
          <div className="section-heading"><div><p className="section-kicker">08 / FORWARD LOOK</p><h2>What can break the setup</h2></div><p>Four variables to monitor next—framed as scenarios, not scheduled-event claims.</p></div>
          <div className="ahead-grid">{outlookItems.map(([number, title, bullets]) => <details key={number}><summary><span>{number}</span><strong>{title}</strong><i>+</i></summary><ul>{bullets.slice(0, 2).map((bullet) => <li key={bullet}>{decodeText(bullet)}</li>)}</ul></details>)}</div>
        </section>

        <section className="macro-reference" aria-label="Macro Reference">
          <div><span>13W T-BILL</span><strong>{formatNumber(tBill.end_price)}%</strong><small>{formatBps(tBill.abs_change)}</small></div>
          <div><span>GOLD</span><strong>${formatNumber(gold.end_price)}</strong><small className={gold.pct_change >= 0 ? "positive" : "negative"}>{formatPct(gold.pct_change)}</small></div>
          <div><span>WTI CRUDE</span><strong>${formatNumber(oil.end_price)}</strong><small className={oil.pct_change >= 0 ? "positive" : "negative"}>{formatPct(oil.pct_change)}</small></div>
          <div><span>RUSSELL 2000</span><strong>{formatNumber(russell.end_price)}</strong><small className={russell.pct_change >= 0 ? "positive" : "negative"}>{formatPct(russell.pct_change)}</small></div>
        </section>

        <aside className="method-note" aria-label="Data freshness and methodology">
          <div><span>DATA FRESHNESS</span><strong>Through {sessionDate.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })} close</strong></div>
          <p>Daily figures compare the latest completed U.S. session with the immediately preceding trading-session close. Market data is sourced from Yahoo Finance and sanity-checked before publication. “Breadth” is the share of the 11 S&amp;P sector ETFs that finished higher.</p>
          <a href="https://finance.yahoo.com/markets/" target="_blank" rel="noreferrer">View source market data ↗</a>
        </aside>

        <footer><div><strong>THE DAILY TAPE</strong><span>Signal over noise.</span></div><div className="footer-meta"><span>DATA: YAHOO FINANCE</span><span>FACT-BASED SUMMARY</span><span>REFRESHED {generatedLabel.toUpperCase()}</span></div></footer>
      </div>
    </main>
  );
}
