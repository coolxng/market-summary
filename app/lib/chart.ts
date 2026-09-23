import type { SessionChart } from "./report";

export type ChartPoint = { label: string; value: number };

const CENTRAL_TIME = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Chicago" });

/**
 * Point labels for an intraday session path. Newer snapshots store epoch
 * timestamps, rendered in Central Time. Older ones only stored exchange-clock
 * strings, so those are labeled with their clock instead of being converted.
 */
export function sessionPoints(chart: SessionChart | null | undefined, usRegularHours: boolean): { points: ChartPoint[]; zoneLabel: string } {
  if (!chart?.closes?.length) return { points: [], zoneLabel: "" };
  if (chart.timestamps?.length === chart.closes.length) {
    return {
      points: chart.closes.map((value, index) => ({ label: `${CENTRAL_TIME.format(new Date(chart.timestamps![index] * 1000))} CT`, value })),
      zoneLabel: "CT",
    };
  }
  const suffix = chart.source === "daily_5d_fallback" ? "" : usRegularHours ? " ET" : " local";
  return {
    points: chart.closes.map((value, index) => ({ label: `${chart.times[index] ?? ""}${suffix}`.trim(), value })),
    zoneLabel: suffix.trim(),
  };
}

export function historyPoints(dates: string[], closes: number[]): ChartPoint[] {
  const format = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  return closes.map((value, index) => ({ label: dates[index] ? format.format(new Date(`${dates[index]}T12:00:00Z`)) : "", value }));
}

export function axisOf(points: ChartPoint[]) {
  if (!points.length) return [];
  return [points[0].label, points[Math.floor(points.length / 2)].label, points.at(-1)!.label];
}

/** Bar size in minutes for an intraday path ("intraday_15m" → 15), or null for daily fallbacks. */
export function intradayMinutes(source: string | undefined) {
  const match = source?.match(/^intraday_(\d+)m$/);
  return match ? Number(match[1]) : null;
}

/** One-month sparkline polyline for a 100×32 box. */
export function sparkPoints(values: number[]) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  return values.map((value, index) => `${(index / (values.length - 1)) * 100},${30 - ((value - min) / span) * 28}`).join(" ");
}
