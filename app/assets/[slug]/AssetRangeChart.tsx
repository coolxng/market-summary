"use client";

import { useState } from "react";
import PriceChart from "../../components/PriceChart";
import type { ChartPoint } from "../../lib/chart";

export type RangeKey = "1D" | "5D" | "1M" | "3M" | "YTD" | "1Y";

export default function AssetRangeChart({
  name,
  ranges,
  initial,
  format,
  changeUnit = "pct",
}: {
  name: string;
  ranges: Array<{ key: RangeKey; points: ChartPoint[]; note: string }>;
  initial: RangeKey;
  format: { prefix?: string; suffix?: string; digits?: number };
  changeUnit?: "pct" | "bps";
}) {
  const [selected, setSelected] = useState<RangeKey>(initial);
  const active = ranges.find((range) => range.key === selected) ?? ranges[0];
  const first = active.points[0]?.value;
  const last = active.points.at(-1)?.value;
  const change = first == null || last == null ? null : changeUnit === "bps" ? (last - first) * 100 : first !== 0 ? ((last - first) / first) * 100 : null;
  const changeText = change == null ? "—" : changeUnit === "bps" ? `${change >= 0 ? "+" : ""}${Math.round(change)} bps` : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`;

  return (
    <div className="asset-range">
      <div className="asset-range__bar">
        <div>
          <span>PRICE PATH · {selected}</span>
          <strong className={change == null ? "" : change > 0 ? "positive" : change < 0 ? "negative" : ""}>
            {changeText}
          </strong>
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
      <PriceChart points={active.points} name={`${name} ${selected}`} format={format} changeUnit={changeUnit === "bps" ? "bps" : "value"} />
    </div>
  );
}
