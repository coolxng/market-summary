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
