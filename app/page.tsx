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
  week_high: number;
  week_low: number;
  ticker_used: string;
  error: string | null;
};

const market = report.market_data as Record<string, MarketDatum>;
const sections = [
  ["brief", "The brief"],
  ["scorecard", "Scorecard"],
  ["sectors", "Sectors"],
  ["macro", "Macro"],
  ["ahead", "Next week"],
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
  const positive = item.pct_change >= 0;
  return (
    <article className="index-card">
      <div className="card-topline">
        <span className="eyebrow">{short}</span>
        <span className={`move ${positive ? "positive" : "negative"}`}>{formatPct(item.pct_change)}</span>
      </div>
      <div className="index-value">{formatNumber(item.end_price)}</div>
      <div className="index-name">{name}</div>
      <Sparkline values={item.closes} positive={positive} />
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
    const saved = window.localStorage.getItem("weekly-tape-theme");
    if (saved === "ink") setTheme("ink");
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("weekly-tape-theme", theme);
  }, [theme]);

  const sectorEntries = useMemo(
    () => Object.entries(report.sector_performance).sort((a, b) => b[1] - a[1]),
    [],
  );
  const sectorAbsMax = Math.max(...sectorEntries.map(([, value]) => Math.abs(value)));
  const sp = market["^GSPC"];
  const nasdaq = market["^IXIC"];
  const vix = market["^VIX"];
  const tenYear = market["^TNX"];
  const dxy = market["DX-Y.NYB"];
  const oil = market["CL=F"];
  const breadth = report.market_breadth;
  const dateStart = new Date(`${report.report_window.start_date}T12:00:00`);
  const dateEnd = new Date(`${report.report_window.end_date}T12:00:00`);
  const dateRange = `${dateStart.toLocaleDateString("en-US", { month: "short", day: "numeric" })} — ${dateEnd.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
  const takeaway = decodeText(report.narrative.takeaway_text);

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="The Weekly Tape home">
          <span className="brand-mark"><i /><i /><i /></span>
          <span>THE WEEKLY TAPE</span>
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
            <span>WEEKLY MARKET INTELLIGENCE</span>
            <span>ISSUE 26.25</span>
            <span>{dateRange.toUpperCase()}</span>
          </div>
          <div className="hero-grid">
            <div className="hero-copy">
              <p className="section-kicker">THE ONE-LINE READ</p>
              <h1>Growth won the week.<br /><em>Breadth never joined.</em></h1>
              <p className="dek">The Nasdaq led a risk-on rebound while equal-weight equities lagged, the dollar strengthened, and crude’s sharp break lower left a more fragile setup than the headline indices suggest.</p>
              <div className="hero-tags">
                <span className="tag up">Risk appetite ↑</span>
                <span className="tag down">Participation ↓</span>
                <span className="tag neutral">Conviction: selective</span>
              </div>
            </div>
            <aside className="regime-card" aria-label="Market regime signals">
              <div className="regime-heading"><span>REGIME MONITOR</span><span className="live-dot">WEEK CLOSED</span></div>
              <Signal label="Risk appetite" value="Constructive" note={`S&P ${formatPct(sp.pct_change)} · VIX ${formatNumber(vix.end_price)}`} tone="good" />
              <Signal label="Participation" value="Narrow" note={`${breadth.advances} of 11 sectors advanced`} tone="warn" />
              <Signal label="Rates impulse" value="Supportive" note={`10Y ${formatNumber(tenYear.end_price)}% · ${formatPct(tenYear.pct_change)}`} tone="good" />
              <Signal label="Dollar impulse" value="Headwind" note={`DXY ${formatPct(dxy.pct_change)} WTD`} tone="warn" />
            </aside>
          </div>
        </section>

        <section className="scorecard section-block" id="scorecard">
          <div className="section-heading">
            <div><p className="section-kicker">01 / SCORECARD</p><h2>The week, at a glance</h2></div>
            <p>Close-to-close performance. Hover or tap each card for the intraweek path.</p>
          </div>
          <div className="index-grid">
            <IndexCard symbol="^GSPC" name="S&P 500" short="SPX" />
            <IndexCard symbol="^IXIC" name="Nasdaq Composite" short="COMP" />
            <IndexCard symbol="^DJI" name="Dow Jones" short="DJIA" />
            <IndexCard symbol="^RUT" name="Russell 2000" short="RUT" />
          </div>
          <div className="pulse-strip">
            <div><span>VOLATILITY</span><strong>{formatNumber(vix.end_price)}</strong><small className="positive">{formatPct(vix.pct_change)}</small></div>
            <div><span>10Y TREASURY</span><strong>{formatNumber(tenYear.end_price)}%</strong><small className="positive">{formatPct(tenYear.pct_change)}</small></div>
            <div><span>U.S. DOLLAR</span><strong>{formatNumber(dxy.end_price)}</strong><small className="negative">{formatPct(dxy.pct_change)}</small></div>
            <div><span>WTI CRUDE</span><strong>${formatNumber(oil.end_price)}</strong><small className="negative">{formatPct(oil.pct_change)}</small></div>
          </div>
        </section>

        <section className="thesis section-block">
          <div className="thesis-label"><span>THE HOUSE VIEW</span><span>3 MIN READ</span></div>
          <blockquote>“The rally was real. The confirmation was not.”</blockquote>
          <p>{takeaway}</p>
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
            <h2>Rates helped.<br />The dollar didn’t.</h2>
            <p>A lower 10-year yield supported duration-sensitive growth, but the stronger dollar and collapsing crude price complicate the clean risk-on story.</p>
            <div className="breadth-meter">
              <div className="meter-head"><span>POSITIVE SECTOR SHARE</span><strong>{breadth.positive_sector_share.toFixed(1)}%</strong></div>
              <div className="meter-track"><span style={{ width: `${breadth.positive_sector_share}%` }} /></div>
              <small>Cap-weighted S&P {formatPct(breadth.spy_pct_change ?? 0)} vs. equal weight {formatPct(breadth.rsp_pct_change ?? 0)}</small>
            </div>
          </div>
          <div className="chart-panel">
            <div className="chart-header"><span>S&P 500 / WEEK PATH</span><strong>{formatNumber(sp.end_price)}</strong></div>
            <Sparkline values={sp.closes} positive={sp.pct_change >= 0} />
            <div className="chart-axis">{sp.dates.map((date) => <span key={date}>{date.split(" ")[0]}</span>)}</div>
            <div className="chart-stats">
              <div><span>WEEK LOW</span><strong>{formatNumber(sp.week_low)}</strong></div>
              <div><span>WEEK HIGH</span><strong>{formatNumber(sp.week_high)}</strong></div>
              <div><span>NASDAQ LEAD</span><strong className="positive">{formatPct(nasdaq.pct_change)}</strong></div>
            </div>
          </div>
        </section>

        <section className="section-block global-section">
          <div className="section-heading">
            <div><p className="section-kicker">04 / GLOBAL CHECK</p><h2>A split tape beyond Wall Street</h2></div>
            <p>Regional closes and weekly direction from the report snapshot.</p>
          </div>
          <div className="global-table" role="table" aria-label="Global market performance">
            <div className="global-row table-head" role="row"><span>MARKET</span><span>REGION</span><span>CLOSE</span><span>WEEK</span></div>
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
            <div><p className="section-kicker">05 / FORWARD LOOK</p><h2>What can break the setup</h2></div>
            <p>Four pressure points to carry into the next session.</p>
          </div>
          <div className="ahead-grid">
            {[
              ["01", "Macro data", report.narrative.lookahead.macro],
              ["02", "Fed & rates", report.narrative.lookahead.fed_policy],
              ["03", "Earnings & AI", report.narrative.lookahead.earnings_and_catalysts],
              ["04", "Risk dashboard", report.narrative.lookahead.risk_factors],
            ].map(([number, title, body]) => (
              <details key={number}>
                <summary><span>{number}</span><strong>{title}</strong><i>+</i></summary>
                <p>{decodeText(body)}</p>
              </details>
            ))}
          </div>
        </section>

        <footer>
          <div><strong>THE WEEKLY TAPE</strong><span>Signal over noise.</span></div>
          <div className="footer-meta"><span>DATA: YFINANCE</span><span>REPORT MODE: {report.report_mode.replaceAll("_", " ").toUpperCase()}</span><span>GENERATED {new Date(report.generated_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }).toUpperCase()}</span></div>
        </footer>
      </div>
    </main>
  );
}
