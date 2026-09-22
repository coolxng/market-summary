"use client";

import { useEffect, useState } from "react";
import styles from "./morning.module.css";

type Quote = {
  name: string;
  symbol: string;
  price: number | null;
  reference_close: number | null;
  pct_change: number | null;
  timestamp: string | null;
  source: string;
  error: string | null;
};

type CalendarEvent = {
  date: string;
  time?: string;
  title?: string;
  ticker?: string;
  country?: string;
  source: string;
};

type Headline = {
  title: string;
  url: string;
  publisher: string;
  published_at?: number | null;
};

export type MorningSnapshot = {
  report_type: "morning_tape";
  market_date: string | null;
  generated_at: string | null;
  status: "ready" | "partial" | "awaiting_first_run";
  data_quality: { valid: number; total: number; coverage_pct: number };
  futures: Record<string, Quote>;
  cross_asset: Record<string, Quote>;
  global_markets: Record<string, Quote>;
  market_calendar: {
    economic: { items: CalendarEvent[]; source: string; error?: string | null };
    earnings: { items: CalendarEvent[]; source: string; error?: string | null };
  };
  market_headlines: {
    items: Headline[];
    source: string;
    label?: string;
    error?: string | null;
  };
  notes: string[];
};

function pct(value: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function price(value: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 10000) return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
  return new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

function QuoteGrid({ items, label }: { items: Record<string, Quote>; label: string }) {
  const entries = Object.values(items);
  if (!entries.length) {
    return <div className={styles.empty}>Awaiting the first scheduled Morning Tape refresh.</div>;
  }
  return (
    <div className={styles.quoteGrid} aria-label={label}>
      {entries.map((item) => (
        <article key={item.symbol}>
          <div><span>{item.symbol}</span><b className={(item.pct_change ?? 0) >= 0 ? "positive" : "negative"}>{pct(item.pct_change)}</b></div>
          <strong>{price(item.price)}</strong>
          <p>{item.name}</p>
          <small>{item.error ? "Unavailable" : item.timestamp ? new Date(item.timestamp).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" }) : "Latest available"}</small>
        </article>
      ))}
    </div>
  );
}

export default function MorningClient({ snapshot }: { snapshot: MorningSnapshot }) {
  const [theme, setTheme] = useState<"paper" | "ink">("paper");

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (window.localStorage.getItem("daily-tape-theme") === "ink") setTheme("ink");
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const toggleTheme = () => {
    const next = theme === "paper" ? "ink" : "paper";
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem("daily-tape-theme", next);
    setTheme(next);
  };

  const events = [
    ...(snapshot.market_calendar?.economic.items ?? []),
    ...(snapshot.market_calendar?.earnings.items ?? []),
  ].sort((a, b) => `${a.date} ${a.time ?? ""}`.localeCompare(`${b.date} ${b.time ?? ""}`));

  const generated = snapshot.generated_at
    ? new Date(snapshot.generated_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" })
    : "Awaiting first run";

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="../" aria-label="The Daily Tape home">
          <span className="brand-mark" style={{ backgroundImage: 'url("https://coolxng.github.io/market-summary/logo.png")' }} />
          <span>THE DAILY TAPE</span>
        </a>
        <nav aria-label="Morning Tape navigation">
          <a href="../">Close</a>
          <a href="./" aria-current="page">Morning</a>
          <a href="../reports/">Archive</a>
          <a href="../search/">Search</a>
        </nav>
        <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
          <span className="theme-toggle__icon" aria-hidden="true">{theme === "paper" ? "◐" : "◑"}</span>
          <span className="theme-toggle__label">{theme === "paper" ? "Ink" : "Paper"}</span>
        </button>
      </header>

      <div className={styles.page}>
        <section className={styles.hero}>
          <div className={styles.issueLine}>
            <span>MORNING MARKET INTELLIGENCE</span>
            <span><b>STATUS</b> {snapshot.status.replaceAll("_", " ").toUpperCase()}</span>
            <span><b>UPDATED</b> {generated.toUpperCase()}</span>
          </div>
          <div className={styles.heroGrid}>
            <div>
              <p className={styles.kicker}>BEFORE THE BELL</p>
              <h1>Know the setup<br /><em>before it moves.</em></h1>
              <p className={styles.dek}>Futures, overnight markets, rates, commodities, crypto, scheduled events, tracked earnings, and source-linked headlines before the U.S. session starts.</p>
            </div>
            <aside className={styles.health}>
              <span>DATA HEALTH</span>
              <strong>{snapshot.data_quality.coverage_pct.toFixed(1)}%</strong>
              <p>{snapshot.data_quality.valid} of {snapshot.data_quality.total || 0} tracked pre-market quotes available.</p>
              <b className={snapshot.status === "ready" ? styles.ready : styles.partial}>{snapshot.status === "ready" ? "Ready" : snapshot.status === "partial" ? "Partial" : "Pending"}</b>
            </aside>
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.heading}><div><p className={styles.kicker}>01 / FUTURES</p><h2>U.S. index setup</h2></div><p>Latest extended-hours/futures quote versus the prior available daily close.</p></div>
          <QuoteGrid items={snapshot.futures} label="U.S. index futures" />
        </section>

        <section className={styles.section}>
          <div className={styles.heading}><div><p className={styles.kicker}>02 / CROSS-ASSET</p><h2>The overnight pressure points</h2></div><p>Volatility, yields, dollar, commodities, and crypto before the cash session.</p></div>
          <QuoteGrid items={snapshot.cross_asset} label="Cross asset markets" />
        </section>

        <section className={styles.section}>
          <div className={styles.heading}><div><p className={styles.kicker}>03 / GLOBAL</p><h2>What traded before New York</h2></div><p>Major overseas equity markets for overnight context.</p></div>
          <QuoteGrid items={snapshot.global_markets} label="Global equity markets" />
        </section>

        <section className={styles.twoCol}>
          <div>
            <div className={styles.headingCompact}><p className={styles.kicker}>04 / CALENDAR</p><h2>On the clock</h2></div>
            <div className={styles.calendar}>
              {events.length ? events.slice(0, 10).map((event, index) => (
                <article key={`${event.date}-${event.title ?? event.ticker}-${index}`}>
                  <div><span>{new Date(`${event.date}T12:00:00`).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}</span><small>{event.time ?? "TBD"}</small></div>
                  <strong>{event.title ?? `${event.ticker} earnings`}</strong>
                  <p>{event.source}</p>
                </article>
              )) : <div className={styles.empty}>Calendar data will populate during the next Morning Tape generation.</div>}
            </div>
          </div>

          <div>
            <div className={styles.headingCompact}><p className={styles.kicker}>05 / HEADLINES</p><h2>Source-linked context</h2></div>
            <div className={styles.news}>
              {snapshot.market_headlines?.items?.length ? snapshot.market_headlines.items.slice(0, 8).map((item) => (
                <a href={item.url} target="_blank" rel="noreferrer" key={item.url}>
                  <span>{item.publisher}</span>
                  <strong>{item.title}</strong>
                  <b>Source ↗</b>
                </a>
              )) : <div className={styles.empty}>Source-linked headlines will populate during the next Morning Tape generation.</div>}
            </div>
          </div>
        </section>

        <aside className={styles.note}>
          <strong>MORNING TAPE METHODOLOGY</strong>
          <p>{snapshot.notes.join(" ")}</p>
        </aside>

        <footer className={styles.footer}>
          <div><strong>THE DAILY TAPE</strong><span>Morning orientation. Close intelligence.</span></div>
          <div><a href="../">Close Tape →</a><a href="../feed.xml">RSS →</a></div>
        </footer>
      </div>
    </main>
  );
}
