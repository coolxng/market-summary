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

type DailyReport = {
  report_type: "daily_market_close";
  session_date: string;
  previous_session_date: string;
  generated_at: string;
  report_mode: string;
  market_data: Record<string, MarketDatum>;
  session_charts: Record<string, SessionChart>;
  daily_sector_performance: Record<string, number>;
  daily_market_breadth: {
    advances: number;
    declines: number;
    positive_sector_share: number;
    spy_pct_change: number | null;
    rsp_pct_change: number | null;
  };
  narrative: {
    daily_takeaway: { what_moved: string; why: string; what_to_watch: string };
    next_session_outlook: Record<"macro" | "fed_policy" | "earnings_and_catalysts" | "risk_factors", string[]>;
  };
};

const dailyReport = report as unknown as DailyReport;
const market = dailyReport.market_data;
const sessionCharts = dailyReport.session_charts;
const sections = [
  ["brief", "The brief"],
  ["scorecard", "Scorecard"],
  ["sectors", "Sectors"],
  ["macro", "Macro"],
  ["ahead", "Next session"],
];

const globalMarkets = [
  ["^N225", "Nikkei 225", "Japan"],
  ["^STOXX50E", "Euro Stoxx 50", "Europe"],
  ["^FTSE", "FTSE 100", "United Kingdom"],
  ["^HSI", "Hang Seng", "Hong Kong"],
] as const;

const cryptoMarkets = [
  ["BTC-USD", "Bitcoin", "BTC"],
  ["ETH-USD", "Ethereum", "ETH"],
  ["SOL-USD", "Solana", "SOL"],
  ["XRP-USD", "XRP", "XRP"],
] as const;

function decodeText(value: string) {
  const named: Record<string, string> = {
    "&amp;": "&", "&quot;": "\"", "&apos;": "'", "&#x27;": "'",
    "&#39;": "'", "&lt;": "<", "&gt;": ">", "&nbsp;": " ",
  };
  return value
    .replace(/&(amp|quot|apos|#x27|#39|lt|gt|nbsp);/g, (match) => named[match] ?? match)
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, num) => String.fromCodePoint(Number(num)))
    .replace(/<\/?strong>/g, "");
}

function formatNumber(value: number, digits = 2) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

function formatPct(value: number) {
  const normalized = Object.is(value, -0) ? 0 : value;
  return `${normalized >= 0 ? "+" : ""}${normalized.toFixed(2)}%`;
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

function IndexCard({ symbol, name, short }: { symbol: string; name: string; short: string }) {
  const item = market[symbol];
  const chart = sessionCharts[symbol];
  const positive = item.pct_change >= 0;
  return (
    <article className="index-card">
      <div className="card-topline">
        <span className="eyebrow">{short}</span>
        <span className={`move ${positive ? "positive" : "negative"}`}>{formatPct(item.pct_change)}</span>
      </div>
      <div className="index-value">{formatNumber(item.end_price)}</div>
      <div className="index-name">{name}</div>
      <Sparkline values={chart?.closes ?? [item.session_open, item.end_price]} positive={positive} />
    </article>
  );
}

function Signal({ label, value, note, tone }: { label: string; value: string; note: string; tone: "good" | "warn" | "neutral" }) {
  return (
    <div className="signal-row">
      <span className={`signal-dot ${tone}`} />
      <div>
        <span className="signal-label">{label}</span>
        <span className="signal-note">{note}</span>
      </div>
      <strong>{value}</strong>
    </div>
  );
}

export default function Home() {
  const [theme, setTheme] = useState<"paper" | "ink">("paper");
  const [assetTab, setAssetTab] = useState<"sectors" | "crypto">("sectors");

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
  const sp = market["^GSPC"];
  const nasdaq = market["^IXIC"];
  const vix = market["^VIX"];
  const tenYear = market["^TNX"];
  const dxy = market["DX-Y.NYB"];
  const oil = market["CL=F"];
  const breadth = dailyReport.daily_market_breadth;
  const sessionDate = new Date(`${dailyReport.session_date}T12:00:00`);
  const previousSessionDate = new Date(`${dailyReport.previous_session_date}T12:00:00`);
  const generatedDate = new Date(`${dailyReport.generated_at.slice(0, 10)}T12:00:00`);
  const sessionDateLabel = sessionDate.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  const previousSessionLabel = previousSessionDate.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const dailyTakeaway = dailyReport.narrative.daily_takeaway;
  const spChart = sessionCharts["^GSPC"];
  const chartTimes = spChart?.times ?? ["9:30 AM", "4:00 PM"];
  const chartAxis = [chartTimes[0], chartTimes[Math.floor(chartTimes.length / 2)], chartTimes.at(-1)].filter(Boolean) as string[];
  const marketDirection = sp.pct_change >= 0 ? "higher" : "lower";
  const breadthDescription = breadth.positive_sector_share >= 60 ? "was broad" : breadth.positive_sector_share <= 40 ? "was narrow" : "was mixed";
  const outlookItems: Array<[string, string, string[]]> = [
    ["01", "Macro data", dailyReport.narrative.next_session_outlook.macro],
    ["02", "Fed & rates", dailyReport.narrative.next_session_outlook.fed_policy],
    ["03", "Earnings & AI", dailyReport.narrative.next_session_outlook.earnings_and_catalysts],
    ["04", "Risk dashboard", dailyReport.narrative.next_session_outlook.risk_factors],
  ];

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="The Daily Tape home">
          <span className="brand-mark"><i /><i /><i /></span>
          <span>THE DAILY TAPE</span>
        </a>
        <nav aria-label="Report sections">
          {sections.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
        </nav>
        <button className="theme-toggle" onClick={() => setTheme(theme === "paper" ? "ink" : "paper")} aria-label={`Switch to ${theme === "paper" ? "dark" : "light"} theme`}>
          <span>{theme === "paper" ? "◐" : "◑"}</span>{theme === "paper" ? "Ink" : "Paper"}
        </button>
      </header>

      <div className="page" id="top">
        <section className="hero" id="brief">
          <div className="issue-line">
            <span>DAILY MARKET CLOSE</span>
            <span>U.S. SESSION</span>
            <span>{sessionDateLabel.toUpperCase()}</span>
          </div>
          <div className="hero-grid">
            <div className="hero-copy">
              <p className="section-kicker">THE ONE-LINE READ</p>
              <h1>Markets closed {marketDirection}.<br /><em>Breadth {breadthDescription}.</em></h1>
              <p className="dek">{decodeText(dailyTakeaway.what_moved)}</p>
              <div className="hero-tags">
                <span className={`tag ${sp.pct_change >= 0 ? "up" : "down"}`}>S&amp;P {formatPct(sp.pct_change)}</span>
                <span className={`tag ${breadth.positive_sector_share >= 50 ? "up" : "down"}`}>{breadth.advances} of 11 sectors advanced</span>
                <span className="tag neutral">Compared with {previousSessionLabel}</span>
              </div>
            </div>
            <aside className="regime-card" aria-label="Market regime signals">
              <div className="regime-heading"><span>SESSION MONITOR</span><span className="live-dot">CLOSE VERIFIED</span></div>
              <Signal label="Index direction" value={sp.pct_change >= 0 ? "Higher" : "Lower"} note={`S&P ${formatPct(sp.pct_change)} · VIX ${formatNumber(vix.end_price)}`} tone={sp.pct_change >= 0 ? "good" : "warn"} />
              <Signal label="Participation" value={breadthDescription.replace("was ", "")} note={`${breadth.advances} of 11 sectors advanced`} tone={breadth.positive_sector_share >= 50 ? "good" : "warn"} />
              <Signal label="Rates move" value={tenYear.pct_change <= 0 ? "Lower" : "Higher"} note={`10Y ${formatNumber(tenYear.end_price)}% · ${formatPct(tenYear.pct_change)}`} tone="neutral" />
              <Signal label="Dollar move" value={dxy.pct_change >= 0 ? "Higher" : "Lower"} note={`DXY ${formatPct(dxy.pct_change)} 1D`} tone="neutral" />
            </aside>
          </div>
        </section>

        <section className="scorecard section-block" id="scorecard">
          <div className="section-heading">
            <div><p className="section-kicker">01 / SCORECARD</p><h2>The session, at a glance</h2></div>
            <p>Current close versus the immediately preceding trading-session close, with regular-hours intraday paths.</p>
          </div>
          <div className="index-grid">
            <IndexCard symbol="^GSPC" name="S&P 500" short="SPX" />
            <IndexCard symbol="^IXIC" name="Nasdaq Composite" short="COMP" />
            <IndexCard symbol="^DJI" name="Dow Jones" short="DJIA" />
            <IndexCard symbol="^RUT" name="Russell 2000" short="RUT" />
          </div>
          <div className="pulse-strip">
            <div><span>VOLATILITY</span><strong>{formatNumber(vix.end_price)}</strong><small className={vix.pct_change >= 0 ? "positive" : "negative"}>{formatPct(vix.pct_change)}</small></div>
            <div><span>10Y TREASURY</span><strong>{formatNumber(tenYear.end_price)}%</strong><small className={tenYear.pct_change >= 0 ? "positive" : "negative"}>{formatPct(tenYear.pct_change)}</small></div>
            <div><span>U.S. DOLLAR</span><strong>{formatNumber(dxy.end_price)}</strong><small className={dxy.pct_change >= 0 ? "positive" : "negative"}>{formatPct(dxy.pct_change)}</small></div>
            <div><span>WTI CRUDE</span><strong>${formatNumber(oil.end_price)}</strong><small className={oil.pct_change >= 0 ? "positive" : "negative"}>{formatPct(oil.pct_change)}</small></div>
          </div>
        </section>

        <section className="thesis section-block">
          <div className="thesis-label"><span>THE HOUSE VIEW</span><span>3 MIN READ</span></div>
          <blockquote>“Observed moves first. Inference second.”</blockquote>
          <p>{decodeText(dailyTakeaway.why)}</p>
        </section>

        <section className="section-block" id="sectors">
          <div className="section-heading">
            <div><p className="section-kicker">02 / LEADERSHIP</p><h2>Where the tape actually moved</h2></div>
            <div className="tabs" role="tablist" aria-label="Asset performance">
              <button className={assetTab === "sectors" ? "active" : ""} onClick={() => setAssetTab("sectors")} role="tab" aria-selected={assetTab === "sectors"}>Sectors</button>
              <button className={assetTab === "crypto" ? "active" : ""} onClick={() => setAssetTab("crypto")} role="tab" aria-selected={assetTab === "crypto"}>Crypto</button>
            </div>
          </div>
          {assetTab === "sectors" ? (
            <div className="sector-board">
              {sectorEntries.map(([name, value], index) => (
                <div className="sector-row" key={name}>
                  <span className="rank">{String(index + 1).padStart(2, "0")}</span>
                  <span className="sector-name">{name}</span>
                  <div className="bar-track"><span className={value >= 0 ? "bar-positive" : "bar-negative"} style={{ width: `${Math.max(5, (Math.abs(value) / sectorAbsMax) * 100)}%` }} /></div>
                  <strong className={value >= 0 ? "positive" : "negative"}>{formatPct(value)}</strong>
                </div>
              ))}
            </div>
          ) : (
            <div className="crypto-board">
              {cryptoMarkets.map(([symbol, name, ticker]) => {
                const item = market[symbol];
                const positive = item.pct_change >= 0;
                return (
                  <article key={symbol}>
                    <div className="coin-head"><span>{ticker}</span><strong className={positive ? "positive" : "negative"}>{formatPct(item.pct_change)}</strong></div>
                    <div className="coin-price">${formatNumber(item.end_price, item.end_price < 10 ? 4 : 0)}</div>
                    <p>{name}</p>
                    <Sparkline values={item.closes} positive={positive} />
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="macro-grid section-block" id="macro">
          <div className="macro-copy">
            <p className="section-kicker">03 / MACRO PULSE</p>
            <h2>Rates moved {tenYear.pct_change >= 0 ? "higher" : "lower"}.<br />The dollar moved {dxy.pct_change >= 0 ? "higher" : "lower"}.</h2>
            <p>The 10-year yield changed {formatPct(tenYear.pct_change)}, DXY changed {formatPct(dxy.pct_change)}, and crude changed {formatPct(oil.pct_change)} during the daily comparison. These are observed moves, not causal claims.</p>
            <div className="breadth-meter">
              <div className="meter-head"><span>POSITIVE SECTOR SHARE</span><strong>{breadth.positive_sector_share.toFixed(1)}%</strong></div>
              <div className="meter-track"><span style={{ width: `${breadth.positive_sector_share}%` }} /></div>
              <small>Cap-weighted S&P {formatPct(breadth.spy_pct_change ?? 0)} vs. equal weight {formatPct(breadth.rsp_pct_change ?? 0)}</small>
            </div>
          </div>
          <div className="chart-panel">
            <div className="chart-header"><span>S&amp;P 500 / REGULAR SESSION</span><strong>{formatNumber(sp.end_price)}</strong></div>
            <Sparkline values={spChart?.closes ?? [sp.session_open, sp.end_price]} positive={sp.pct_change >= 0} />
            <div className="chart-axis">{chartAxis.map((time, index) => <span key={`${time}-${index}`}>{time}</span>)}</div>
            <div className="chart-stats">
              <div><span>DAY LOW</span><strong>{formatNumber(sp.day_low)}</strong></div>
              <div><span>DAY HIGH</span><strong>{formatNumber(sp.day_high)}</strong></div>
              <div><span>NASDAQ 1D</span><strong className={nasdaq.pct_change >= 0 ? "positive" : "negative"}>{formatPct(nasdaq.pct_change)}</strong></div>
            </div>
            <small className="chart-source">{spChart?.source === "intraday_5m" ? "Regular-hours 5-minute data" : "Session open/close fallback"}</small>
          </div>
        </section>

        <section className="section-block global-section">
          <div className="section-heading">
            <div><p className="section-kicker">04 / GLOBAL CHECK</p><h2>A split tape beyond Wall Street</h2></div>
            <p>Latest completed daily closes around the represented U.S. session.</p>
          </div>
          <div className="global-table" role="table" aria-label="Global market performance">
            <div className="global-row table-head" role="row"><span>MARKET</span><span>REGION</span><span>CLOSE</span><span>1D</span></div>
            {globalMarkets.map(([symbol, name, region]) => {
              const item = market[symbol];
              const unavailable = Boolean(item.error);
              return (
                <div className="global-row" role="row" key={symbol}>
                  <strong>{name}</strong><span>{region}</span>
                  <span>{unavailable ? "Unavailable" : formatNumber(item.end_price)}</span>
                  <strong className={unavailable ? "muted" : item.pct_change >= 0 ? "positive" : "negative"}>{unavailable ? "—" : formatPct(item.pct_change)}</strong>
                </div>
              );
            })}
          </div>
        </section>

        <section className="section-block ahead" id="ahead">
          <div className="section-heading">
            <div><p className="section-kicker">05 / NEXT SESSION OUTLOOK</p><h2>What to watch next</h2></div>
            <p>Four pressure points to carry into the next session.</p>
          </div>
          <div className="ahead-grid">
            {outlookItems.map(([number, title, body]) => (
              <details key={number}>
                <summary><span>{number}</span><strong>{title}</strong><i>+</i></summary>
                <p>{body.map((item) => decodeText(item)).join(" ")}</p>
              </details>
            ))}
          </div>
        </section>

        <footer>
          <div><strong>THE DAILY TAPE</strong><span>One completed session. Signal over noise.</span></div>
          <div className="footer-meta"><span>DATA: YFINANCE</span><span>REPORT MODE: {dailyReport.report_mode.replaceAll("_", " ").toUpperCase()}</span><span>SESSION {sessionDateLabel.toUpperCase()}</span><span>GENERATED {generatedDate.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }).toUpperCase()}</span></div>
        </footer>
      </div>
    </main>
  );
}
