import { isFiniteNumber } from "./report";

export type RegimeKey = "constructive" | "mixed" | "defensive" | "unavailable";

export const REGIME_LABEL: Record<RegimeKey, string> = {
  constructive: "Constructive",
  mixed: "Mixed",
  defensive: "Defensive",
  unavailable: "Unavailable",
};

const SIGNAL_TO_REGIME: Record<string, RegimeKey> = {
  risk_on_confirmed: "constructive",
  risk_off_confirmed: "defensive",
  mixed: "mixed",
};

export const EXPECTED_SECTORS = 11;

/**
 * The generator's rule (generate_report.build_editorial_context): constructive
 * needs S&P up, VIX down, full sector coverage and >=60% of sectors positive;
 * defensive mirrors it at <=40%; everything else is mixed.
 */
export function applyRegimeRule(sp: number | null, vix: number | null, sectorReturns: number[]): RegimeKey {
  if (!isFiniteNumber(sp) || !isFiniteNumber(vix)) return "unavailable";
  const full = sectorReturns.length === EXPECTED_SECTORS;
  const share = sectorReturns.length ? (sectorReturns.filter((value) => value > 0).length / sectorReturns.length) * 100 : null;
  if (sp > 0 && vix < 0 && full && share != null && share >= 60) return "constructive";
  if (sp < 0 && vix > 0 && full && share != null && share <= 40) return "defensive";
  return "mixed";
}

type RegimeSource = {
  derived_metrics?: { risk_confirmation?: { signal?: string } };
  market_data?: Record<string, { pct_change?: number | null; error?: string | null } | undefined>;
  daily_sector_performance?: Record<string, number>;
};

/** Stored classification when present; otherwise the same rule on the issue's own stored data. */
export function classifyRegime(report: RegimeSource): { regime: RegimeKey; basis: "published" | "derived" | "unavailable" } {
  const stored = report.derived_metrics?.risk_confirmation?.signal;
  if (stored && SIGNAL_TO_REGIME[stored]) return { regime: SIGNAL_TO_REGIME[stored], basis: "published" };
  const row = (symbol: string) => {
    const value = report.market_data?.[symbol];
    return value && !value.error && isFiniteNumber(value.pct_change) ? value.pct_change : null;
  };
  const regime = applyRegimeRule(row("^GSPC"), row("^VIX"), Object.values(report.daily_sector_performance ?? {}).filter(isFiniteNumber));
  return { regime, basis: regime === "unavailable" ? "unavailable" : "derived" };
}

export type RegimeEntry = {
  date: string;
  regime: RegimeKey;
  basis: "published" | "reconstructed" | "derived" | "unavailable";
  sp500: number | null;
  vix: number | null;
  positive: number | null;
  valid: number | null;
  href?: string;
};

type TimelineSource = RegimeSource & {
  session_date: string;
  regime_history?: { sessions: Array<{ date: string; signal: string; sp500_pct: number | null; vix_pct: number | null; sectors_positive: number; sectors_valid: number }> };
};

function fromIssue(report: TimelineSource, href?: string): RegimeEntry {
  const { regime, basis } = classifyRegime(report);
  const pct = (symbol: string) => {
    const row = report.market_data?.[symbol];
    return row && !row.error && isFiniteNumber(row.pct_change) ? row.pct_change : null;
  };
  const sectors = Object.values(report.daily_sector_performance ?? {}).filter(isFiniteNumber);
  return {
    date: report.session_date,
    regime,
    basis,
    sp500: pct("^GSPC"),
    vix: pct("^VIX"),
    positive: sectors.length ? sectors.filter((value) => value > 0).length : null,
    valid: sectors.length || null,
    href,
  };
}

/**
 * Up to `sessions` regime classifications ending at `latest.session_date`.
 * Classifications published in an archived issue (or the latest issue) win;
 * other days come from the generator's reconstruction with the same rule.
 * Nothing after the latest issue's own date is used.
 */
export function buildRegimeTimeline(
  latest: TimelineSource,
  archive: Array<{ report: TimelineSource; href: string }>,
  sessions = 60,
): RegimeEntry[] {
  const byDate = new Map<string, RegimeEntry>();
  for (const row of latest.regime_history?.sessions ?? []) {
    if (row.date > latest.session_date) continue;
    byDate.set(row.date, {
      date: row.date,
      regime: SIGNAL_TO_REGIME[row.signal] ?? "unavailable",
      basis: SIGNAL_TO_REGIME[row.signal] ? "reconstructed" : "unavailable",
      sp500: row.sp500_pct,
      vix: row.vix_pct,
      positive: row.sectors_positive,
      valid: row.sectors_valid,
    });
  }
  for (const { report, href } of archive) {
    if (report.session_date > latest.session_date) continue;
    byDate.set(report.session_date, fromIssue(report, href));
  }
  byDate.set(latest.session_date, { ...fromIssue(latest), href: byDate.get(latest.session_date)?.href });
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date)).slice(-sessions);
}
