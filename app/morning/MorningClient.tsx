import SiteHeader from "../components/SiteHeader";
import MarketCalendarList from "../components/MarketCalendarList";
import CatalystList from "../components/CatalystList";
import { calendarOf, catalystsOf, type CatalystSet, type DailyReport } from "../lib/report";
import styles from "./morning.module.css";

type Quote = {
  name: string;
  symbol: string;
  price: number | null;
  reference_close: number | null;
  reference_date?: string | null;
  pct_change: number | null;
  timestamp: string | null;
  stale?: boolean;
  source: string;
  error: string | null;
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
  market_calendar?: DailyReport["market_calendar"];
  verified_catalysts?: CatalystSet;
  market_headlines?: DailyReport["market_headlines"];
  what_matters_today?: string[];
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
          <div>
            <span>{item.symbol}</span>
            <b className={item.pct_change == null ? "" : item.pct_change >= 0 ? "positive" : "negative"}>{pct(item.pct_change)}</b>
          </div>
          <strong>{price(item.price)}</strong>
          <p>{item.name}</p>
          <small>
            {item.error
              ? "Unavailable"
              : item.stale
                ? "Stale · previous close only"
                : item.timestamp
                  ? new Date(item.timestamp).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" })
                  : "Latest available"}
          </small>
        </article>
      ))}
    </div>
  );
}

export default function MorningClient({ snapshot }: { snapshot: MorningSnapshot }) {
  const calendar = calendarOf(snapshot);
  const catalysts = catalystsOf(snapshot);

  const generated = snapshot.generated_at
    ? new Date(snapshot.generated_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Chicago", timeZoneName: "short" })
    : "Awaiting first run";

  return (
    <main id="main">
      <SiteHeader root="../" current="morning" />

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

        {!!snapshot.what_matters_today?.length && (
          <section className={styles.matters} aria-label="What matters today">
            <div className={styles.mattersHead}>
              <p className={styles.kicker}>WHAT MATTERS TODAY</p>
              <span>Observed setup only</span>
            </div>
            <div className={styles.mattersGrid}>
              {snapshot.what_matters_today.slice(0, 3).map((item, index) => (
                <article key={item}><span>{String(index + 1).padStart(2, "0")}</span><p>{item}</p></article>
              ))}
            </div>
          </section>
        )}

        <section className={styles.section}>
          <div className={styles.heading}><div><p className={styles.kicker}>01 / FUTURES</p><h2>U.S. index setup</h2></div><p>Latest extended-hours/futures quote versus the latest completed daily reference close.</p></div>
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

        <section className={styles.section} id="calendar">
          <div className={styles.heading}><div><p className={styles.kicker}>04 / TODAY&apos;S CALENDAR</p><h2>On the clock</h2></div><p>U.S. releases, Treasury auctions, tracked earnings and market-structure dates for today and the next session. Times in Central Time.</p></div>
          <MarketCalendarList calendar={calendar} currentLabel="Today" emptyNote={snapshot.generated_at ? undefined : "Calendar data will populate during the first Morning Tape generation."} />
        </section>

        <section className={styles.section} id="catalysts">
          <div className={styles.heading}><div><p className={styles.kicker}>05 / OVERNIGHT CATALYSTS</p><h2>On the record overnight</h2></div><p>Published since the prior U.S. close by official sources or allowlisted publishers. Context only, never a claimed cause.</p></div>
          <CatalystList catalysts={catalysts} assetBaseHref="../assets/" />
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
