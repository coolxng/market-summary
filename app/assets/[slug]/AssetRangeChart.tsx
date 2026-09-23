"use client";

import { useCallback, useState } from "react";
import PriceChart from "../../components/PriceChart";
import RollingNumber from "../../components/RollingNumber";
import type { ChartPoint } from "../../lib/chart";
import { formatNumber } from "../../lib/format";
import { useAssetHover, useHoveredPoint } from "./AssetQuote";

export type RangeKey = "1D" | "5D" | "1M" | "3M" | "YTD" | "1Y";

function changeOf(value: number, base: number | null | undefined, unit: "pct" | "bps") {
  if (base == null) return null;
  return unit === "bps" ? value - base : base !== 0 ? ((value - base) / base) * 100 : null;
}

function changeLabel(change: number | null, unit: "pct" | "bps") {
  if (change == null) return "—";
  return unit === "bps" ? `${change >= 0 ? "+" : ""}${Math.round(change * 100)} bps` : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`;
}

function toneOf(change: number | null) {
  return change == null || change === 0 ? "" : change > 0 ? "positive" : "negative";
}

export default function AssetRangeChart({
  name,
  ranges,
  initial,
  format,
  changeUnit = "pct",
  dayBase,
  latest,
}: {
  name: string;
  ranges: Array<{ key: RangeKey; points: ChartPoint[]; note: string }>;
  initial: RangeKey;
  format: { prefix?: string; suffix?: string; digits?: number };
  changeUnit?: "pct" | "bps";
  /** Previous close: the 1D move (header, hover and reference line) is measured from it, like the headline 1D change. */
  dayBase?: number | null;
  /** Latest close, shown in the phone readout when nothing is inspected. */
  latest?: number | null;
}) {
  const [selected, setSelected] = useState<RangeKey>(initial);
  const active = ranges.find((range) => range.key === selected) ?? ranges[0];
  const base = selected === "1D" && dayBase != null ? dayBase : active.points[0]?.value;
  const last = active.points.at(-1)?.value;
  const change = last == null ? null : changeOf(last, base, changeUnit);
  const stroke = change == null || change === 0 ? "var(--ink-soft)" : change > 0 ? "var(--up)" : "var(--down)";

  const setHovered = useAssetHover();
  const hovered = useHoveredPoint();
  const follow = useCallback((point: ChartPoint | null, start: ChartPoint | null) => {
    if (!setHovered) return;
    if (!point) return setHovered(null);
    const from = selected === "1D" && dayBase != null ? dayBase : start?.value;
    setHovered({ label: point.label, value: point.value, change: changeOf(point.value, from, changeUnit === "bps" ? "bps" : "pct"), range: selected });
  }, [setHovered, changeUnit, selected, dayBase]);

  // Phone readout: the hero quote scrolls out of view, so the chart carries its own.
  const readoutValue = hovered?.value ?? latest ?? last ?? null;
  const readoutChange = hovered ? hovered.change : change;
  const readoutPrice = readoutValue == null ? "—" : `${format.prefix ?? ""}${formatNumber(readoutValue, format.digits ?? 2)}${format.suffix ?? ""}`;
  const readoutText = changeLabel(readoutChange, changeUnit);

  return (
    <div className="asset-range">
      <div className="asset-range__readout" aria-hidden="true">
        <span>{hovered ? hovered.label.toUpperCase() : selected === "1D" ? "LATEST CLOSE" : `LATEST · ${selected}`}</span>
        <strong><RollingNumber value={readoutPrice} /></strong>
        <b className={toneOf(readoutChange)}>{readoutText}</b>
      </div>
      <div className="asset-range__bar">
        <div>
          <span>PRICE PATH · {selected}{selected === "1D" && dayBase != null ? " · VS PREV CLOSE" : ""}</span>
          <strong className={toneOf(change)}>{changeLabel(change, changeUnit)}</strong>
          <small>{active.note}</small>
        </div>
        <div className="asset-range__buttons" role="group" aria-label="Chart range">
          {ranges.map((range) => (
            <button
              key={range.key}
              type="button"
              aria-pressed={range.key === selected}
              disabled={range.points.length < 2}
              onClick={() => setSelected(range.key)}
            >
              {range.key}
            </button>
          ))}
        </div>
      </div>
      <PriceChart
        points={active.points}
        name={`${name} ${selected}`}
        format={format}
        stroke={stroke}
        area
        baseline={selected === "1D" ? dayBase : null}
        changeUnit={changeUnit === "bps" ? "bps" : "value"}
        onActiveChange={follow}
      />
    </div>
  );
}
