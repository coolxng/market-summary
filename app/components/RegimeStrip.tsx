"use client";

import { useState } from "react";
import type { RegimeEntry } from "../lib/regime";
import { REGIME_LABEL } from "../lib/regime";

const BASIS_LABEL: Record<RegimeEntry["basis"], string> = {
  published: "Published in that day's issue",
  derived: "Derived from that issue's stored data",
  reconstructed: "Reconstructed from daily closes, same rule",
  unavailable: "Inputs unavailable",
};

function pct(value: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function dateLabel(date: string, options: Intl.DateTimeFormatOptions = { weekday: "short", month: "short", day: "numeric", year: "numeric" }) {
  return new Intl.DateTimeFormat("en-US", { ...options, timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
}

function describe(entry: RegimeEntry) {
  return `${dateLabel(entry.date)}: ${REGIME_LABEL[entry.regime]}. S&P 500 ${pct(entry.sp500)}, VIX ${pct(entry.vix)}, ${entry.valid != null ? `${entry.positive} of ${entry.valid} sectors up` : "sector data unavailable"}. ${BASIS_LABEL[entry.basis]}.`;
}

/** Session-by-session regime strip. Hover, focus or tap a day to see its inputs. */
export default function RegimeStrip({ entries, hrefBase, rule }: { entries: RegimeEntry[]; hrefBase?: string; rule?: string }) {
  const [activeDate, setActiveDate] = useState<string | null>(null);
  if (!entries.length) return <p className="data-empty">No regime history is stored yet.</p>;
  const active = entries.find((entry) => entry.date === activeDate) ?? entries.at(-1)!;
  const counts = entries.reduce<Record<string, number>>((acc, entry) => ({ ...acc, [entry.regime]: (acc[entry.regime] ?? 0) + 1 }), {});
  const published = entries.filter((entry) => entry.basis === "published" || entry.basis === "derived").length;

  return (
    <div className="regime-strip">
      <div className="regime-strip__summary">
        <span>LAST {entries.length} SESSION{entries.length === 1 ? "" : "S"}</span>
        <strong>
          <b className="regime-count regime-count--constructive">{counts.constructive ?? 0} constructive</b>
          <b className="regime-count">{counts.mixed ?? 0} mixed</b>
          <b className="regime-count regime-count--defensive">{counts.defensive ?? 0} defensive</b>
          {counts.unavailable ? <b className="regime-count">{counts.unavailable} unavailable</b> : null}
        </strong>
      </div>
      <div className="regime-strip__track" style={{ maxWidth: `${entries.length * 44}px` }}>
        <ol className="regime-strip__cells" aria-label="Regime by session, oldest to newest">
          {entries.map((entry) => {
            const className = `regime-cell regime-cell--${entry.regime}${entry.basis === "reconstructed" ? " regime-cell--reconstructed" : ""}${entry.date === active.date ? " is-active" : ""}`;
            const props = {
              className,
              "aria-label": describe(entry),
              onMouseEnter: () => setActiveDate(entry.date),
              onFocus: () => setActiveDate(entry.date),
            };
            return (
              <li key={entry.date}>
                {entry.href && hrefBase != null
                  ? <a href={`${hrefBase}${entry.href}`} {...props} />
                  : <button type="button" {...props} onClick={() => setActiveDate(entry.date)} />}
              </li>
            );
          })}
        </ol>
        <div className="regime-strip__axis" aria-hidden="true"><span>{dateLabel(entries[0].date, { month: "short", day: "numeric" })}</span><span>{dateLabel(entries.at(-1)!.date, { month: "short", day: "numeric" })}</span></div>
      </div>
      <div className="regime-strip__readout" aria-live="polite">
        <strong className={`regime-label regime-label--${active.regime}`}>{REGIME_LABEL[active.regime]}</strong>
        <span>{dateLabel(active.date)}</span>
        <span>S&amp;P 500 {pct(active.sp500)} · VIX {pct(active.vix)} · {active.valid != null ? `${active.positive}/${active.valid} sectors up` : "sectors unavailable"}</span>
        <em>{BASIS_LABEL[active.basis]}</em>
      </div>
      <p className="regime-strip__note">
        Solid cells were published in an archived issue ({published}); outlined cells are reconstructed from daily closes with the same rule, using only that day&apos;s moves.
        {rule ? ` ${rule}` : ""}
      </p>
    </div>
  );
}
