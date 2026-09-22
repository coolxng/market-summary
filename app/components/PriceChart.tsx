"use client";

import { useId, useState } from "react";
import type { ChartPoint } from "../lib/chart";
import { axisOf } from "../lib/chart";

type ValueFormat = { prefix?: string; suffix?: string; digits?: number };

function formatValue(value: number, format: ValueFormat) {
  const digits = format.digits ?? (Math.abs(value) < 10 ? 4 : 2);
  const number = new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
  return `${format.prefix ?? ""}${number}${format.suffix ?? ""}`;
}

/**
 * Inspectable line chart: pointer/touch hover, arrow-key stepping, and a
 * data-table fallback for screen readers. No chart library; one SVG polyline.
 */
export default function PriceChart({
  points,
  name,
  format = {},
  stroke = "var(--accent)",
  size = "large",
  emptyText = "No verified path is stored for this range.",
  changeUnit = "value",
}: {
  points: ChartPoint[];
  name: string;
  format?: ValueFormat;
  stroke?: string;
  size?: "large" | "panel";
  emptyText?: string;
  /** How the first-to-last change is described: in the value's own units or in basis points (yields). */
  changeUnit?: "value" | "bps";
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();

  if (points.length < 2) return <div className={`price-chart price-chart--${size} price-chart--empty`}>{emptyText}</div>;

  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const coords = values.map((value, index) => ({ x: (index / (values.length - 1)) * 100, y: 92 - ((value - min) / span) * 82 }));
  const polyline = coords.map(({ x, y }) => `${x},${y}`).join(" ");
  const active = activeIndex == null ? null : { ...points[activeIndex], ...coords[activeIndex] };
  const change = values.at(-1)! - values[0];
  const summary = `${name}: ${points[0].label} ${formatValue(values[0], format)} to ${points.at(-1)!.label} ${formatValue(values.at(-1)!, format)}; low ${formatValue(min, format)}, high ${formatValue(max, format)}.`;

  const setFromPointer = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    setActiveIndex(Math.round(ratio * (values.length - 1)));
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const last = values.length - 1;
    const step = event.shiftKey ? Math.max(1, Math.round(values.length / 10)) : 1;
    const current = activeIndex ?? last;
    const next = event.key === "Home" ? 0 : event.key === "End" ? last
      : event.key === "ArrowLeft" ? Math.max(0, current - step)
      : event.key === "ArrowRight" ? Math.min(last, current + step) : null;
    if (next == null) {
      if (event.key === "Escape") setActiveIndex(null);
      return;
    }
    event.preventDefault();
    setActiveIndex(next);
  };

  return (
    <figure className={`price-chart price-chart--${size}`}>
      <div
        className="price-chart__canvas"
        role="group"
        tabIndex={0}
        aria-label={`${summary} Use arrow keys to inspect points; Shift moves faster.`}
        onPointerMove={setFromPointer}
        onPointerDown={setFromPointer}
        onPointerLeave={() => setActiveIndex(null)}
        onFocus={() => setActiveIndex((index) => index ?? values.length - 1)}
        onBlur={() => setActiveIndex(null)}
        onKeyDown={onKeyDown}
      >
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <line x1="0" x2="100" y1={coords[0].y} y2={coords[0].y} className="price-chart__baseline" vectorEffect="non-scaling-stroke" />
          <polyline points={polyline} fill="none" stroke={stroke} strokeWidth="2" vectorEffect="non-scaling-stroke" />
          {active && <line x1={active.x} x2={active.x} y1="4" y2="96" className="price-chart__crosshair" vectorEffect="non-scaling-stroke" />}
        </svg>
        {active && <i className="price-chart__dot" style={{ left: `${active.x}%`, top: `${active.y}%` }} aria-hidden="true" />}
        {active && (
          <div className="price-chart__tooltip" style={{ left: `${Math.min(88, Math.max(12, active.x))}%` }}>
            <span>{active.label}</span>
            <strong>{formatValue(active.value, format)}</strong>
          </div>
        )}
        <p className="visually-hidden" aria-live="polite">{active ? `${active.label}: ${formatValue(active.value, format)}` : ""}</p>
      </div>
      <div className="price-chart__axis" aria-hidden="true">{axisOf(points).map((label, index) => <span key={`${label}-${index}`}>{label}</span>)}</div>
      <figcaption className="price-chart__caption">
        <span>
          Low {formatValue(min, format)} · High {formatValue(max, format)} · {points.length} points
          <b className={change > 0 ? "positive" : change < 0 ? "negative" : ""}> · Range change {change >= 0 ? "+" : "−"}{changeUnit === "bps" ? `${Math.round(Math.abs(change) * 100)} bps` : formatValue(Math.abs(change), format)}</b>
        </span>
        <button type="button" onClick={() => setShowTable((value) => !value)} aria-expanded={showTable} aria-controls={tableId}>
          {showTable ? "Hide data" : "View data"}
        </button>
      </figcaption>
      {showTable && (
        <div className="price-chart__table" id={tableId}>
          <table>
            <caption className="visually-hidden">{name} data</caption>
            <thead><tr><th scope="col">Time / date</th><th scope="col">Value</th></tr></thead>
            <tbody>
              {points.map((point, index) => <tr key={`${point.label}-${index}`}><td>{point.label}</td><td>{formatValue(point.value, format)}</td></tr>)}
            </tbody>
          </table>
        </div>
      )}
    </figure>
  );
}
