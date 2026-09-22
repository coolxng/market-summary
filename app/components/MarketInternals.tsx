import type { DailyReport, SectorAdLine, TrendParticipation } from "../lib/report";
import { formatPp, formatSessionDate, toneClass } from "../lib/format";

function AdLine({ line }: { line: SectorAdLine }) {
  const max = Math.max(1, ...line.net_advancing.map((value) => Math.abs(value)));
  const width = 100 / line.net_advancing.length;
  const last = line.cumulative.at(-1) ?? 0;
  const summary = `Sector advance-decline line over ${line.dates.length} sessions from ${formatSessionDate(line.dates[0], { month: "short", day: "numeric" })} to ${formatSessionDate(line.dates.at(-1)!, { month: "short", day: "numeric" })}: cumulative net advancing sector ETFs ${last >= 0 ? "+" : ""}${last}.`;
  return (
    <figure className="ad-line">
      <figcaption>
        <span>SECTOR ADVANCE / DECLINE · {line.dates.length} SESSIONS</span>
        <strong className={toneClass(last)}>{last >= 0 ? "+" : ""}{last}</strong>
        <small>Cumulative net advancing sector ETFs. {line.basis}.</small>
      </figcaption>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={summary}>
        <line x1="0" x2="100" y1="20" y2="20" className="ad-line__zero" vectorEffect="non-scaling-stroke" />
        {line.net_advancing.map((value, index) => {
          const height = (Math.abs(value) / max) * 18;
          return (
            <rect key={line.dates[index]} x={index * width + width * 0.18} width={width * 0.64} y={value >= 0 ? 20 - height : 20} height={Math.max(height, 0.4)} className={value > 0 ? "ad-line__up" : value < 0 ? "ad-line__down" : "ad-line__flat"}>
              <title>{`${formatSessionDate(line.dates[index], { month: "short", day: "numeric" })}: net ${value >= 0 ? "+" : ""}${value}, cumulative ${line.cumulative[index] >= 0 ? "+" : ""}${line.cumulative[index]}`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="ad-line__axis" aria-hidden="true"><span>{formatSessionDate(line.dates[0], { month: "short", day: "numeric" })}</span><span>{formatSessionDate(line.dates.at(-1)!, { month: "short", day: "numeric" })}</span></div>
    </figure>
  );
}

/** Concise participation read built only from transparent tracked universes. */
export default function MarketInternals({ report }: { report: DailyReport }) {
  const breadth = report.daily_market_breadth;
  const internals = report.market_internals;
  const trend = internals?.trend_participation;
  const highLow = internals?.tracked_high_low;
  const weighting = internals?.equal_weight_vs_cap_weight_pp;
  const sectorCount = Object.keys(report.daily_sector_performance).length;
  const oneDayGap = weighting?.["1d"] ?? (breadth.rsp_pct_change != null && breadth.spy_pct_change != null ? breadth.rsp_pct_change - breadth.spy_pct_change : null);
  const notCovered = internals?.not_covered ?? [];

  const trendCells: Array<[string, TrendParticipation | null | undefined]> = [
    ["ABOVE 20-DAY", trend?.above_20d],
    ["ABOVE 50-DAY", trend?.above_50d],
    ["ABOVE 200-DAY", trend?.above_200d],
  ];

  return (
    <>
      <div className="internals-grid internals-grid--today">
        <article>
          <span>SECTORS ADVANCING</span>
          <strong>{breadth.advances}<small> / {sectorCount}</small></strong>
          <p>{breadth.declines} declined · {breadth.positive_sector_share.toFixed(1)}% positive{sectorCount < 11 ? ` · ${11 - sectorCount} not verified` : ""}</p>
        </article>
        <article>
          <span>EQUAL VS CAP WEIGHT · 1D</span>
          <strong className={toneClass(oneDayGap)}>{formatPp(oneDayGap)}</strong>
          <p>RSP minus SPY. {oneDayGap == null ? "Unavailable." : oneDayGap > 0 ? "Equal weight led." : oneDayGap < 0 ? "Cap weight led." : "Matched."}</p>
        </article>
        <article>
          <span>EQUAL VS CAP · 5D / 1M</span>
          <strong><b className={toneClass(weighting?.["5d"])}>{formatPp(weighting?.["5d"], 1)}</b> <i>/</i> <b className={toneClass(weighting?.["1m"])}>{formatPp(weighting?.["1m"], 1)}</b></strong>
          <p>{weighting ? "Total-return spread. Persistent positives favor broader participation." : "Not recorded for this issue."}</p>
        </article>
        <article>
          <span>20-SESSION HIGHS / LOWS</span>
          <strong>{highLow ? <><b className={highLow.new_20d_highs ? "positive" : ""}>{highLow.new_20d_highs}</b> <i>/</i> <b className={highLow.new_20d_lows ? "negative" : ""}>{highLow.new_20d_lows}</b></> : "—"}</strong>
          <p>{highLow ? `Closing highs vs lows across ${highLow.valid} tracked instruments.` : "Not recorded for this issue."}</p>
        </article>
        {trendCells.map(([label, metric]) => (
          <article key={label}>
            <span>SECTORS {label}</span>
            <strong>{metric ? `${metric.share_pct.toFixed(0)}%` : "—"}</strong>
            <p>{metric ? `${metric.above} of ${metric.valid} sector ETFs above their moving average.` : "Not recorded for this issue."}</p>
          </article>
        ))}
        <article className="internals-grid__line">
          {internals?.sector_ad_line ? <AdLine line={internals.sector_ad_line} /> : <p>The sector advance/decline line needs 20 shared sessions for all 11 sector ETFs; it is not recorded for this issue.</p>}
        </article>
      </div>
      <p className="internals-note">
        Universes: 11 S&amp;P sector ETFs; SPY and RSP; 20-session highs and lows across sector ETFs, tracked mega-caps, SPY, RSP, QQQ and IWM.
        {notCovered.length > 0 && <> Not covered by current data sources: {notCovered.join("; ")}. These are left out rather than approximated.</>}
      </p>
    </>
  );
}
