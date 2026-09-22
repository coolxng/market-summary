// Shared shapes for generated Daily Tape snapshots. Older archived snapshots are
// missing many optional fields; readers must treat absence as "not recorded",
// never as zero.

export type MarketDatum = {
  dates: string[];
  closes: number[];
  end_price: number | null;
  pct_change: number | null;
  abs_change: number | null;
  prev_close: number | null;
  session_open: number | null;
  day_high: number | null;
  day_low: number | null;
  session_date: string | null;
  previous_session_date: string | null;
  ticker_used: string;
  data_source?: string;
  source_symbol?: string;
  error: string | null;
};

/** A market row whose close was verified for its session. */
export type VerifiedDatum = MarketDatum & {
  end_price: number;
  pct_change: number;
  abs_change: number;
  prev_close: number;
};

export type SessionChart = {
  times: string[];
  timestamps?: number[];
  time_zone?: string;
  closes: number[];
  source: "intraday_5m" | "daily_ohlc_fallback" | "daily_5d_fallback";
  session_date: string;
  error: string | null;
};

export type MegaCapSnapshot = { name: string; result: MarketDatum; session_chart?: SessionChart };

export type EditorialReading = { observed: string; interpretation: string };
export type EditorialBrief = {
  headline: string;
  opening_summary: string;
  regime: EditorialReading;
  sector_leadership: EditorialReading;
  megacap_leadership: EditorialReading;
  macro_read: EditorialReading;
  investor_takeaway: EditorialReading;
  watchlist: string[];
};

export type FeedStatus = {
  id: string;
  name: string;
  source_url: string;
  status: "ok" | "empty" | "unavailable" | "disabled";
  as_of: string | null;
  error: string | null;
};

export type CalendarItem = {
  date: string;
  time?: string | null;
  time_status?: "scheduled" | "all_day" | "tentative" | "tbd";
  starts_at?: string;
  source_time?: string | null;
  source_time_zone?: string | null;
  title: string;
  category?: string;
  kind?: "economic" | "auction" | "earnings" | "market_structure";
  country?: string;
  importance?: string | number | null;
  actual?: string | number | null;
  consensus?: string | number | null;
  previous?: string | number | null;
  detail?: string | null;
  ticker?: string;
  date_status?: "listed" | "estimated_window";
  rule_based?: boolean;
  session?: "current" | "next" | "between";
  source: string;
  source_url?: string;
};

export type MarketCalendar = {
  window?: { current_session: string | null; next_session: string; display_time_zone: string };
  items: CalendarItem[];
  feeds: FeedStatus[];
  note?: string;
};

export type Catalyst = {
  title: string;
  url: string;
  publisher: string;
  published_at: number | null;
  category?: string;
  source_type?: "official" | "news";
  related_tickers?: string[];
};

export type CatalystSet = {
  window?: { start: string; end: string };
  items: Catalyst[];
  feeds: FeedStatus[];
  label?: string;
};

export type DataQuality = {
  status: "healthy" | "degraded" | "limited";
  overall?: "verified" | "partial" | "limited";
  valid: number;
  total: number;
  coverage_pct: number;
  issues: string[];
  sources: Record<string, number>;
  checked_session: string;
  feeds?: FeedStatus[];
  unavailable_feeds?: string[];
  local_sessions?: Record<string, string>;
};

export type CurvePoint = { value: number; change_bp: number | null };
export type TreasuryRates = FeedStatus & {
  curve: { as_of: string; previous_date: string | null; tenors: Record<string, CurvePoint> } | null;
  spreads: Record<string, { value_bp: number; change_bp: number | null } | null>;
  real: { as_of: string; previous_date?: string | null; tenors: Record<string, CurvePoint> } | null;
  real_source_url?: string;
};
export type CreditSpreads = FeedStatus & {
  series: Record<string, { name: string; series_id: string; value_bp: number; change_bp: number | null; as_of: string; source_url: string }>;
};
export type SectorAdLine = { dates: string[]; net_advancing: number[]; cumulative: number[]; universe: string; basis: string };

export type RelativeStrengthRow = {
  symbol: string;
  name: string;
  group: "Sector" | "Large cap";
  "1d": number | null;
  "5d": number | null;
  "1m": number | null;
  persistence: "leading" | "lagging" | "mixed" | "incomplete";
};
export type RegimeSession = {
  date: string;
  signal: "risk_on_confirmed" | "risk_off_confirmed" | "mixed" | "unavailable";
  sp500_pct: number | null;
  vix_pct: number | null;
  sectors_positive: number;
  sectors_valid: number;
  basis: "reconstructed";
};

export type TrendParticipation = { above: number; valid: number; share_pct: number };

export type AssetHistory = {
  symbol: string;
  dates: string[];
  closes: number[];
  returns: Record<string, number | null>;
  moving_averages: Record<string, number | null>;
  above_moving_average: Record<string, boolean | null>;
  source: string;
  as_of: string | null;
  error: string | null;
};

type LegacyFeed<T> = { items: T[]; source: string; as_of: string | null; error: string | null };

export type DailyReport = {
  report_type: "daily_market_close";
  session_date: string;
  previous_session_date: string;
  generated_at: string;
  report_mode: string;
  derived_metrics?: { risk_confirmation?: { signal: string } };
  data_quality?: DataQuality;
  market_calendar?: MarketCalendar | { economic: LegacyFeed<CalendarItem>; earnings: LegacyFeed<CalendarItem>; note?: string };
  verified_catalysts?: CatalystSet;
  market_headlines?: LegacyFeed<Catalyst> & { label?: string };
  rates_credit?: Record<string, MarketDatum | number | null> & { official_curve?: TreasuryRates; credit_spreads?: CreditSpreads };
  market_internals?: {
    trend_participation: {
      above_20d: TrendParticipation | null;
      above_50d: TrendParticipation | null;
      above_200d: TrendParticipation | null;
      universe: string;
    };
    tracked_high_low?: { new_20d_highs: number; new_20d_lows: number; valid: number; universe: string };
    sector_relative_strength_vs_spy: Record<string, Record<string, number | null>>;
    benchmark_returns: Record<string, number | null>;
    equal_weight_vs_cap_weight_pp?: Record<"1d" | "5d" | "1m", number | null>;
    sector_ad_line?: SectorAdLine | null;
    not_covered?: string[];
    limitation: string;
  };
  asset_history?: Record<string, AssetHistory>;
  relative_strength?: { benchmark: string; unit: string; windows: Record<string, string>; rows: RelativeStrengthRow[] };
  regime_history?: { rule: string; note: string; sessions: RegimeSession[] };
  market_data: Record<string, MarketDatum>;
  session_charts: Record<string, SessionChart>;
  mega_cap_data?: Record<string, MegaCapSnapshot>;
  sector_data?: Record<string, MarketDatum>;
  daily_sector_performance: Record<string, number>;
  daily_market_breadth: {
    advances: number;
    declines: number;
    positive_sector_share: number;
    spy_pct_change: number | null;
    rsp_pct_change: number | null;
  };
  narrative: {
    editorial?: EditorialBrief;
    megacap_descriptions: Record<string, string>;
    crypto_descriptions: Record<"btc" | "eth" | "sol" | "xrp", string>;
    daily_takeaway: { what_moved: string; why: string; what_to_watch: string };
    next_session_outlook: Record<"macro" | "fed_policy" | "earnings_and_catalysts" | "risk_factors", string[]>;
  };
};

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function verified(item: MarketDatum | null | undefined): VerifiedDatum | null {
  if (!item || item.error) return null;
  if (!isFiniteNumber(item.end_price) || item.end_price <= 0) return null;
  if (!isFiniteNumber(item.pct_change) || !isFiniteNumber(item.prev_close) || !isFiniteNumber(item.abs_change)) return null;
  return item as VerifiedDatum;
}

/** Calendar items from current or legacy snapshots; undefined when never captured. */
export function calendarOf(report: { market_calendar?: DailyReport["market_calendar"] }): MarketCalendar | undefined {
  const calendar = report.market_calendar;
  if (!calendar) return undefined;
  if ("items" in calendar) return calendar;
  const legacy = [...(calendar.economic?.items ?? []), ...(calendar.earnings?.items ?? [])]
    .filter((item) => item.title || item.ticker)
    .map((item) => ({ ...item, title: item.title ?? `${item.ticker} earnings` }));
  return {
    items: legacy.sort((a, b) => `${a.date} ${a.time ?? ""}`.localeCompare(`${b.date} ${b.time ?? ""}`)),
    feeds: [calendar.economic, calendar.earnings].filter(Boolean).map((feed, index) => ({
      id: index ? "legacy_earnings" : "legacy_economic",
      name: feed.source,
      source_url: "",
      status: feed.items.length ? "ok" : feed.error ? "unavailable" : "empty",
      as_of: feed.as_of,
      error: feed.error,
    })),
    note: calendar.note,
  };
}

export function catalystsOf(report: { verified_catalysts?: CatalystSet; market_headlines?: DailyReport["market_headlines"] }): CatalystSet | undefined {
  if (report.verified_catalysts) return report.verified_catalysts;
  const legacy = report.market_headlines;
  if (!legacy) return undefined;
  return {
    items: legacy.items,
    feeds: [{
      id: "legacy_headlines",
      name: legacy.source,
      source_url: "",
      status: legacy.items.length ? "ok" : legacy.error ? "unavailable" : "empty",
      as_of: legacy.as_of,
      error: legacy.error,
    }],
    label: legacy.label,
  };
}
