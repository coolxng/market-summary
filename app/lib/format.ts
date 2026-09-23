const CENTRAL = "America/Chicago";

export function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

export function formatPct(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) return "—";
  const normalized = Object.is(value, -0) || Math.abs(value) < 0.5 * 10 ** -digits ? 0 : value;
  return `${normalized >= 0 ? "+" : ""}${normalized.toFixed(digits)}%`;
}

export function formatPp(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)} pp`;
}

/** Yield changes arrive in percentage points; display them as basis points. */
export function formatBpsFromPoints(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  const bps = Math.round(value * 100);
  return `${bps >= 0 ? "+" : ""}${bps} bps`;
}

export function formatBps(value: number | null | undefined, digits = 0) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)} bps`;
}

export function toneClass(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value) || value === 0) return "";
  return value > 0 ? "positive" : "negative";
}

export function formatSessionDate(date: string, options: Intl.DateTimeFormatOptions = { month: "long", day: "numeric", year: "numeric" }) {
  return new Intl.DateTimeFormat("en-US", { ...options, timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
}

export function formatCentralTime(epochSeconds: number) {
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: CENTRAL, timeZoneName: "short" })
    .format(new Date(epochSeconds * 1000));
}

export function formatCentralDateTime(value: string | number | Date) {
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: CENTRAL, timeZoneName: "short",
  }).format(date);
}

export function centralDateKey(epochSeconds: number) {
  const parts = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: CENTRAL })
    .format(new Date(epochSeconds * 1000));
  return parts;
}

export function decodeText(value: string) {
  const named: Record<string, string> = {
    "&amp;": "&", "&quot;": "\"", "&apos;": "'", "&#x27;": "'",
    "&#39;": "'", "&lt;": "<", "&gt;": ">", "&nbsp;": " ",
  };
  let decoded = value;
  for (let pass = 0; pass < 3; pass += 1) {
    const next = decoded
      .replace(/&(amp|quot|apos|#x27|#39|lt|gt|nbsp);/g, (match) => named[match] ?? match)
      .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
      .replace(/&#(\d+);/g, (_, num) => String.fromCodePoint(Number(num)));
    if (next === decoded) break;
    decoded = next;
  }
  return decoded.replace(/<\/?strong>/g, "");
}

/**
 * Feed-supplied URL, only if it is plain http(s); anything else (javascript:,
 * data:, relative paths) becomes undefined so it is never rendered as a link.
 */
export function safeHref(value: string | null | undefined) {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : undefined;
  } catch {
    return undefined;
  }
}
