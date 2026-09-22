import SiteHeader from "../components/SiteHeader";
import MarketCalendarList from "../components/MarketCalendarList";
import CatalystList from "../components/CatalystList";
import EditionFreshness from "../components/EditionFreshness";
import { FeedHealthList } from "../components/DataStatus";
import { assetBySymbol } from "../lib/assets";
import { calendarOf, catalystsOf, type CatalystSet, type DailyReport, type FeedStatus } from "../lib/report";
import { formatBps, formatCentralDateTime, formatNumber, formatPct, formatSessionDate, toneClass } from "../lib/format";
import styles from "./morning.module.css";

type Quote = {
  name: string;
  symbol: string;
  region?: string;
  proxy?: boolean;
  note?: string;
  price: number | null;
  reference_close: number | null;
  reference_date?: string | null;
  pct_change: number | null;
  timestamp: string | null;
  age_minutes?: number | null;
  stale?: boolean;
  delayed?: boolean;
  source: string;
  error: string | null;
};

type CurvePoint = { value: number; change_bp: number | null };
type TreasuryRates = FeedStatus & {
  curve: { as_of: string; previous_date: string | null; tenors: Record<string, CurvePoint> } | null;
  spreads: Record<string, { value_bp: number; change_bp: number | null } | null>;
  real: { as_of: string; tenors: Record<string, CurvePoint> } | null;
  real_source_url?: string;
};

export type MorningSnapshot = {
  report_type: "morning_tape";
  market_date: string | null;
  trading_day?: boolean;
  previous_session?: string;
  generated_at: string | null;
  status: "ready" | "partial" | "awaiting_first_run";
  data_quality: { valid: number; total: number; coverage_pct: number; delayed?: string[]; feeds?: FeedStatus[] };
  futures: Record<string, Quote>;
  cross_asset: Record<string, Quote>;
  global_markets: Record<string, Quote>;
  treasury_rates?: TreasuryRates | null;
  market_calendar?: DailyReport["market_calendar"] | null;
  verified_catalysts?: CatalystSet | null;
  market_headlines?: DailyReport["market_headlines"];
  what_matters_today?: Array<{ label: string; text: string } | string>;
  notes: string[];
};

const YIELD_SYMBOLS = new Set(["^TNX", "2YY=F"]);

function quoteMove(item: Quote) {
  if (item.pct_change == null || item.price == null || item.reference_close == null) return null;
  if (YIELD_SYMBOLS.has(item.symbol)) return { text: formatBps((item.price - item.reference_close) * 100), value: item.price - item.reference_close };
  return { text: formatPct(item.pct_change), value: item.pct_change };
}

function quotePrice(item: Quote) {
  if (item.price == null) return "—";
  if (YIELD_SYMBOLS.has(item.symbol)) return `${formatNumber(item.price, 3)}%`;
  if (Math.abs(item.price) >= 10000) return formatNumber(item.price, 0);
  return formatNumber(item.price, Math.abs(item.price) < 10 ? 4 : 2);
}

function freshness(item: Quote, marketDate: string | null) {
  if (item.error) return { label: "Unavailable", tone: "down" };
  if (item.stale) return { label: `Previous close only${item.reference_date ? ` · ${item.reference_date}` : ""}`, tone: "muted" };
  const when = item.timestamp ? formatCentralDateTime(item.timestamp) : "Time not provided";
  const sameDay = item.timestamp && marketDate && item.timestamp.slice(0, 10) === marketDate;
  if (item.delayed) return { label: `Delayed · last ${when}`, tone: "accent" };
  return { label: sameDay ? `As of ${when.split(", ").at(-1)}` : `As of ${when}`, tone: "muted" };
}

function QuoteGrid({ items, label, marketDate }: { items: Record<string, Quote>; label: string; marketDate: string | null }) {
  const entries = Object.values(items);
  if (!entries.length) return <p className={styles.empty}>No quotes were recorded for this edition.</p>;
  return (
    <div className={styles.quoteGrid} role="list" aria-label={label}>
      {entries.map((item) => {
        const move = quoteMove(item);
        const state = freshness(item, marketDate);
        const asset = assetBySymbol[item.symbol];
        return (
          <article key={item.symbol} role="listitem">
            <div>
              <span>{item.symbol}{item.proxy && <i className={styles.proxy}>Proxy</i>}</span>
              <b className={move ? toneClass(move.value) : "muted"}>{move?.text ?? "—"}</b>
            </div>
            <strong>{quotePrice(item)}</strong>
            <p>{asset ? <a href={`../assets/${asset.slug}/`}>{item.name}</a> : item.name}</p>
            <small className={styles[`state_${state.tone}`]}>{state.label}</small>
            {item.note && <small className={styles.quoteNote}>{item.note}</small>}
          </article>
        );
      })}
    </div>
  );
}

function RatesBoard({ rates }: { rates: TreasuryRates | null | undefined }) {
  if (!rates) return <p className={styles.empty}>Official Treasury rates were not recorded for this edition.</p>;
  if (!rates.curve) return <p className={styles.empty}>The U.S. Treasury yield curve was unavailable when this edition was generated. No substitute yields are shown.</p>;
  const tenors: Array<[string, string]> = [["3m", "3M"], ["2y", "2Y"], ["5y", "5Y"], ["10y", "10Y"], ["30y", "30Y"]];
  const spreads: Array<[string, string]> = [["2s10s", "2s10s"], ["3m10y", "3M–10Y"]];
  return (
    <>
      <div className={styles.ratesGrid}>
        {tenors.map(([key, label]) => {
          const point = rates.curve?.tenors[key];
          return (
            <div key={key}>
              <span>{label} TREASURY</span>
              <strong>{point ? `${point.value.toFixed(2)}%` : "—"}</strong>
              <b className={toneClass(point?.change_bp)}>{point ? `${formatBps(point.change_bp)} d/d` : "Not published"}</b>
            </div>
          );
        })}
        {spreads.map(([key, label]) => {
          const spread = rates.spreads[key];
          return (
            <div key={key}>
              <span>{label} CURVE</span>
              <strong>{spread ? formatBps(spread.value_bp) : "—"}</strong>
              <b className={toneClass(spread?.change_bp)}>{spread ? `${formatBps(spread.change_bp)} d/d` : "Not published"}</b>
            </div>
          );
        })}
        <div>
          <span>10Y REAL (TIPS PAR)</span>
          <strong>{rates.real?.tenors["10y"] ? `${rates.real.tenors["10y"].value.toFixed(2)}%` : "—"}</strong>
          <b className={toneClass(rates.real?.tenors["10y"]?.change_bp)}>{rates.real?.tenors["10y"] ? `${formatBps(rates.real.tenors["10y"].change_bp)} d/d` : "Not published"}</b>
        </div>
      </div>
      <p className={styles.sourceLine}>
        Official end-of-day par yields as of <strong>{formatSessionDate(rates.curve.as_of, { weekday: "short", month: "short", day: "numeric" })}</strong>
        {rates.curve.previous_date && <> versus {formatSessionDate(rates.curve.previous_date, { month: "short", day: "numeric" })}</>}.{" "}
        <a href={rates.source_url} target="_blank" rel="noopener noreferrer" data-outbound="source">U.S. Treasury ↗</a>
      </p>
    </>
  );
}

export default function MorningTape({ snapshot }: { snapshot: MorningSnapshot }) {
  const calendar = snapshot.market_calendar ? calendarOf({ market_calendar: snapshot.market_calendar }) : undefined;
  const catalysts = catalystsOf({ verified_catalysts: snapshot.verified_catalysts ?? undefined, market_headlines: snapshot.market_headlines });
  const awaiting = !snapshot.generated_at;
  const generated = snapshot.generated_at ? formatCentralDateTime(snapshot.generated_at) : "Awaiting first run";
  const matters = (snapshot.what_matters_today ?? []).map((item) => typeof item === "string" ? { label: "", text: item } : item);
  const statusLabel = snapshot.status === "ready" ? "Ready" : snapshot.status === "partial" ? "Partial" : "Pending";
  const feeds = snapshot.data_quality.feeds ?? [];

  return (
    <main id="main">
      <SiteHeader root="../" current="morning" />
      <div className={styles.page}>
        <section className={styles.hero}>
          <div className={styles.issueLine}>
            <span>MORNING TAPE</span>
            <span><b>EDITION</b> {snapshot.market_date ? formatSessionDate(snapshot.market_date, { weekday: "short", month: "short", day: "numeric", year: "numeric" }).toUpperCase() : "PENDING"}</span>
            <span><b>GENERATED</b> {generated.toUpperCase()}</span>
          </div>
          <EditionFreshness editionDate={snapshot.market_date} label="Morning Tape" />
          <div className={styles.heroGrid}>
            <div>
              <p className={styles.kicker}>BEFORE THE BELL</p>
              <h1>Know the setup<br /><em>before it moves.</em></h1>
              <p className={styles.dek}>Futures, overnight markets, the official Treasury curve, the dollar, commodities, crypto, today&apos;s calendar and overnight developments before the U.S. session opens.</p>
            </div>
            <aside className={styles.health} aria-label="Morning data health">
              <span>QUOTE COVERAGE</span>
              <strong>{snapshot.data_quality.total ? `${snapshot.data_quality.coverage_pct.toFixed(0)}%` : "—"}</strong>
              <p>{snapshot.data_quality.valid} of {snapshot.data_quality.total} tracked quotes returned a current price.{snapshot.data_quality.delayed?.length ? ` Delayed: ${snapshot.data_quality.delayed.join(", ")}.` : ""}</p>
              <b className={snapshot.status === "ready" ? styles.ready : styles.partial}>{statusLabel}</b>
            </aside>
          </div>
        </section>

        {awaiting ? (
          <section className={styles.section}>
            <p className={styles.empty}>The Morning Tape has not been generated yet. It publishes at about 7:45 AM Central on NYSE trading days. Until then, nothing is shown in place of live data.</p>
          </section>
        ) : (
          <>
            {snapshot.trading_day === false && (
              <p className="edition-warning" role="status"><strong>Markets closed.</strong> {formatSessionDate(snapshot.market_date!, { weekday: "long", month: "short", day: "numeric" })} is not an NYSE trading day.</p>
            )}

            <section className={styles.matters} aria-labelledby="matters-title">
              <div className={styles.mattersHead}>
                <p className={styles.kicker} id="matters-title">WHAT MATTERS TODAY</p>
                <span>Observed setup · no forecasts</span>
              </div>
              {matters.length ? (
                <div className={styles.mattersGrid}>
                  {matters.map((item, index) => (
                    <article key={`${item.label}-${index}`}>
                      <span>{item.label ? item.label.toUpperCase() : String(index + 1).padStart(2, "0")}</span>
                      <p>{item.text}</p>
                    </article>
                  ))}
                </div>
              ) : <p className={styles.empty}>Not enough verified data was available to summarize this morning.</p>}
            </section>

            <section className={styles.section} id="futures" aria-labelledby="futures-title">
              <div className={styles.heading}><div><p className={styles.kicker}>01 / FUTURES</p><h2 id="futures-title">U.S. index setup</h2></div><p>Latest E-mini quote versus the prior daily close. Quotes older than 90 minutes are marked delayed.</p></div>
              <QuoteGrid items={snapshot.futures} label="U.S. index futures" marketDate={snapshot.market_date} />
            </section>

            <section className={styles.section} id="overnight" aria-labelledby="overnight-title">
              <div className={styles.heading}><div><p className={styles.kicker}>02 / OVERNIGHT</p><h2 id="overnight-title">What traded before New York</h2></div><p>Asia has closed its session; Europe is usually trading at publication. Each move is measured from that market&apos;s prior close.</p></div>
              <QuoteGrid items={snapshot.global_markets} label="Global equity markets" marketDate={snapshot.market_date} />
            </section>

            <section className={styles.section} id="cross-asset" aria-labelledby="cross-title">
              <div className={styles.heading}><div><p className={styles.kicker}>03 / CROSS-ASSET</p><h2 id="cross-title">The pressure points</h2></div><p>Volatility, rates proxies, the dollar, commodities and crypto. Yield rows show basis-point changes.</p></div>
              <QuoteGrid items={snapshot.cross_asset} label="Cross-asset markets" marketDate={snapshot.market_date} />
            </section>

            <section className={styles.section} id="rates" aria-labelledby="rates-title">
              <div className={styles.heading}><div><p className={styles.kicker}>04 / TREASURY CURVE</p><h2 id="rates-title">The official close</h2></div><p>The latest U.S. Treasury par yield curve. It is published once a day, so it reflects the prior session, not overnight trading.</p></div>
              <RatesBoard rates={snapshot.treasury_rates} />
            </section>

            <section className={styles.section} id="calendar" aria-labelledby="calendar-title">
              <div className={styles.heading}><div><p className={styles.kicker}>05 / TODAY&apos;S CALENDAR</p><h2 id="calendar-title">On the clock</h2></div><p>U.S. releases, Treasury auctions, tracked earnings and market-structure dates for today and the next session. Times in Central Time.</p></div>
              <MarketCalendarList calendar={calendar} currentLabel="Today" />
            </section>

            <section className={styles.section} id="catalysts" aria-labelledby="catalysts-title">
              <div className={styles.heading}><div><p className={styles.kicker}>06 / OVERNIGHT CATALYSTS</p><h2 id="catalysts-title">On the record overnight</h2></div><p>Published since the prior U.S. close by official sources or allowlisted publishers. Context only, never a claimed cause.</p></div>
              <CatalystList catalysts={catalysts} assetBaseHref="../assets/" />
            </section>
          </>
        )}

        <aside className={styles.note} aria-label="Morning Tape methodology and sources">
          <strong>METHODOLOGY &amp; SOURCES</strong>
          <div>
            <p>{snapshot.notes.join(" ")}</p>
            <FeedHealthList feeds={feeds} />
          </div>
        </aside>

        <footer className={styles.footer}>
          <div><strong>THE DAILY TAPE</strong><span>Morning orientation. Close intelligence.</span></div>
          <div><a href="../">Close Tape →</a><a href="../reports/">Archive →</a><a href="../feed.xml">RSS →</a></div>
        </footer>
      </div>
    </main>
  );
}
