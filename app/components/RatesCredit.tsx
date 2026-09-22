import type { DailyReport, MarketDatum } from "../lib/report";
import { verified } from "../lib/report";
import { formatBps, formatBpsFromPoints, formatNumber, formatPct, formatSessionDate, toneClass } from "../lib/format";

function asRow(value: unknown) {
  return value && typeof value === "object" && "end_price" in value ? verified(value as MarketDatum) : null;
}

function AsOf({ date, reportDate }: { date: string | null | undefined; reportDate: string }) {
  if (!date) return null;
  const label = formatSessionDate(date, { month: "short", day: "numeric" });
  return <small className={date < reportDate ? "rates-asof rates-asof--lag" : "rates-asof"}>as of {label}{date < reportDate ? " (prior session)" : ""}</small>;
}

/**
 * Rates and credit, separated by what each number actually is: Cboe yield
 * indexes from the session, the official Treasury par curve (dated), actual
 * option-adjusted credit spreads (dated) and bond ETF prices as proxies.
 */
export default function RatesCredit({ report, assetBaseHref }: { report: DailyReport; assetBaseHref: string }) {
  const rates = report.rates_credit ?? {};
  const market = report.market_data;
  const official = rates.official_curve;
  const curve = official?.curve ?? null;
  const credit = rates.credit_spreads;
  const session = {
    "3m": asRow(rates["3m"]) ?? verified(market["^IRX"]),
    "5y": asRow(rates["5y"]),
    "10y": asRow(rates["10y"]) ?? verified(market["^TNX"]),
    "30y": asRow(rates["30y"]),
  } as Record<string, ReturnType<typeof verified>>;
  const tenors: Array<[string, string, string | null]> = [["3m", "3M", "us-3m"], ["2y", "2Y", null], ["5y", "5Y", "us-5y"], ["10y", "10Y", "us-10y"], ["30y", "30Y", "us-30y"]];
  const fiveTen = typeof rates["5s10s_bp"] === "number" ? rates["5s10s_bp"] as number : null;
  const proxies: Array<[string, string, string, ReturnType<typeof verified>]> = [
    ["HYG", "High-yield corporate bond ETF", "hyg", asRow(rates.hyg)],
    ["LQD", "Investment-grade corporate bond ETF", "lqd", asRow(rates.lqd)],
    ["TIP", "TIPS bond ETF", "tip", asRow(rates.tip)],
  ];
  const move = asRow(rates.move);

  return (
    <div className="rates-board">
      <div className="rates-block">
        <div className="subsection-head"><span>TREASURY YIELDS</span><small>SESSION CLOSE (CBOE INDEX) · OFFICIAL PAR CURVE (U.S. TREASURY)</small></div>
        <table className="rates-table">
          <thead>
            <tr><th scope="col">Tenor</th><th scope="col">Session close</th><th scope="col">1D</th><th scope="col">Official par</th><th scope="col">d/d</th></tr>
          </thead>
          <tbody>
            {tenors.map(([key, label, slug]) => {
              const row = session[key];
              const point = curve?.tenors[key];
              return (
                <tr key={key}>
                  <th scope="row">{slug ? <a href={`${assetBaseHref}${slug}/`}>{label}</a> : label}</th>
                  <td>{row ? `${formatNumber(row.end_price, 3)}%` : <span className="muted">No index</span>}</td>
                  <td className={toneClass(row?.abs_change)}>{row ? formatBpsFromPoints(row.abs_change) : "—"}</td>
                  <td>{point ? `${point.value.toFixed(2)}%` : "—"}</td>
                  <td className={toneClass(point?.change_bp)}>{point ? formatBps(point.change_bp) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="rates-foot">
          {curve ? <>Official curve <AsOf date={curve.as_of} reportDate={report.session_date} />. Treasury publishes it late in the afternoon, so the Close Tape can show the prior session. </> : official ? "The official Treasury curve was unavailable at generation; no substitute is shown. " : "The official Treasury curve was not recorded for this issue. "}
          {official?.source_url && <a href={official.source_url} target="_blank" rel="noopener noreferrer" data-outbound="source">U.S. Treasury ↗</a>}
        </p>
      </div>

      <div className="rates-block rates-cells">
        <div className="subsection-head"><span>CURVE</span><small>BASIS POINTS</small></div>
        {([["2s10s", "2s10s", "2Y → 10Y"], ["3m10y", "3M–10Y", "3M → 10Y"], ["5s30s", "5s30s", "5Y → 30Y"]] as const).map(([key, title, label]) => {
          const spread = official?.spreads?.[key];
          return (
            <article key={key}>
              <span>{title}</span>
              <strong>{spread ? formatBps(spread.value_bp) : "—"}</strong>
              <b className={toneClass(spread?.change_bp)}>{spread ? `${formatBps(spread.change_bp)} d/d` : "Not recorded"}</b>
              <small>{label} · official curve{curve ? <> <AsOf date={curve.as_of} reportDate={report.session_date} /></> : ""}</small>
            </article>
          );
        })}
        <article>
          <span>5s10s</span>
          <strong>{fiveTen == null ? "—" : formatBps(fiveTen, 1)}</strong>
          <b className="muted">Session close</b>
          <small>5Y → 10Y · Cboe yield indexes</small>
        </article>
      </div>

      <div className="rates-block rates-cells">
        <div className="subsection-head"><span>CREDIT</span><small>SPREADS ARE ACTUAL OAS · ETF ROWS ARE PRICE PROXIES</small></div>
        {([["hy_oas", "HIGH-YIELD OAS"], ["ig_oas", "INVESTMENT-GRADE OAS"]] as const).map(([key, label]) => {
          const series = credit?.series?.[key];
          return (
            <article key={key}>
              <span>{label}</span>
              <strong>{series ? `${series.value_bp.toFixed(0)} bps` : "—"}</strong>
              <b className={toneClass(series?.change_bp == null ? null : -series.change_bp)}>{series ? `${formatBps(series.change_bp)} d/d` : credit ? "Unavailable" : "Not recorded"}</b>
              <small>{series ? <><a href={series.source_url} target="_blank" rel="noopener noreferrer" data-outbound="source">{series.name} · FRED ↗</a> <AsOf date={series.as_of} reportDate={report.session_date} /></> : "ICE BofA option-adjusted spread via FRED"}</small>
            </article>
          );
        })}
        {proxies.slice(0, 2).map(([symbol, label, slug, row]) => (
          <a key={symbol} href={`${assetBaseHref}${slug}/`}>
            <span>{symbol} <i className="proxy-tag">ETF proxy</i></span>
            <strong>{row ? `$${formatNumber(row.end_price)}` : "—"}</strong>
            <b className={toneClass(row?.pct_change)}>{row ? `${formatPct(row.pct_change)} price` : "Not recorded"}</b>
            <small>{label}. A price, not a spread.</small>
          </a>
        ))}
      </div>

      <div className="rates-block rates-cells">
        <div className="subsection-head"><span>REAL YIELDS &amp; RATE VOLATILITY</span><small>TREASURY REAL PAR CURVE · ICE BOFA MOVE</small></div>
        {(["5y", "10y"] as const).map((tenor) => {
          const point = official?.real?.tenors?.[tenor];
          return (
            <article key={tenor}>
              <span>{tenor.toUpperCase()} REAL YIELD</span>
              <strong>{point ? `${point.value.toFixed(2)}%` : "—"}</strong>
              <b className={toneClass(point?.change_bp)}>{point ? `${formatBps(point.change_bp)} d/d` : "Not recorded"}</b>
              <small>Treasury real par curve{official?.real ? <> <AsOf date={official.real.as_of} reportDate={report.session_date} /></> : ""}</small>
            </article>
          );
        })}
        <a href={`${assetBaseHref}tip/`}>
          <span>TIP <i className="proxy-tag">ETF proxy</i></span>
          <strong>{proxies[2][3] ? `$${formatNumber(proxies[2][3].end_price)}` : "—"}</strong>
          <b className={toneClass(proxies[2][3]?.pct_change)}>{proxies[2][3] ? `${formatPct(proxies[2][3].pct_change)} price` : "Not recorded"}</b>
          <small>TIPS bond ETF price, not a real yield.</small>
        </a>
        <a href={`${assetBaseHref}move/`}>
          <span>MOVE INDEX</span>
          <strong>{move ? formatNumber(move.end_price) : "—"}</strong>
          <b className={toneClass(move?.pct_change)}>{move ? formatPct(move.pct_change) : "Not recorded"}</b>
          <small>Treasury implied volatility · Yahoo Finance</small>
        </a>
      </div>
    </div>
  );
}
