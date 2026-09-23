"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import RollingNumber from "../../components/RollingNumber";
import { formatBpsFromPoints, formatNumber, formatPct, toneClass } from "../../lib/format";

/** The chart point under the cursor, with its move from the start of the visible range. */
export type HoveredPoint = { label: string; value: number; change: number | null; range: string };

const HoverContext = createContext<{ hovered: HoveredPoint | null; setHovered: (point: HoveredPoint | null) => void } | null>(null);

/** Shares the chart's hovered point with the quote block in the page hero. */
export function AssetHoverProvider({ children }: { children: ReactNode }) {
  const [hovered, setHovered] = useState<HoveredPoint | null>(null);
  const value = useMemo(() => ({ hovered, setHovered }), [hovered]);
  return <HoverContext.Provider value={value}>{children}</HoverContext.Provider>;
}

export function useAssetHover() {
  return useContext(HoverContext)?.setHovered;
}

export function useHoveredPoint() {
  return useContext(HoverContext)?.hovered ?? null;
}

/**
 * Hero price: the latest close at rest, the hovered chart point while the chart
 * is inspected. Digits roll between values rather than swapping.
 */
export default function AssetQuote({
  label,
  value,
  change,
  changeUnit,
  format,
  className,
  children,
}: {
  label: string;
  value: number | null;
  /** 1D move: percent, or percentage points for yields (shown as bps). */
  change: number | null;
  changeUnit: "pct" | "bps";
  format: { prefix?: string; suffix?: string; digits?: number };
  className?: string;
  children?: ReactNode;
}) {
  const hovered = useContext(HoverContext)?.hovered ?? null;
  const shown = hovered ? hovered.value : value;
  const shownChange = hovered ? hovered.change : change;
  const price = shown == null ? "—" : `${format.prefix ?? ""}${formatNumber(shown, format.digits ?? 2)}${format.suffix ?? ""}`;
  const move = changeUnit === "bps" ? formatBpsFromPoints(shownChange) : formatPct(shownChange);

  return (
    <div className={className} data-hovering={hovered ? "" : undefined}>
      <span>{hovered ? hovered.label.toUpperCase() : label}</span>
      <strong><RollingNumber value={price} /></strong>
      <b className={toneClass(shownChange)}>{move} <small>{hovered ? hovered.range : "1D"}</small></b>
      {children}
    </div>
  );
}
