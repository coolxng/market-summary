import report from "../../data/report_snapshot.json";
import { assetCatalog, isYieldAsset, logoUrl, type AssetDefinition } from "./assets";
import { quoteRow, verified, type DailyReport } from "./report";
import { formatBpsFromPoints, formatNumber, formatPct, toneClass } from "./format";

const dailyReport = report as unknown as DailyReport;

/** Everything a list row needs for one asset in the latest issue. Serializable, so it can be passed to client components. */
export type AssetSummary = {
  slug: string;
  symbol: string;
  name: string;
  category: AssetDefinition["category"];
  logo: string | null;
  price: number | null;
  priceText: string;
  /** One-day move: percent, or percentage points for yields. */
  change: number | null;
  changeText: string;
  tone: string;
  /** Up to one month of daily closes, oldest first. */
  spark: number[];
  sparkTone: string;
};

export function formatAssetPrice(asset: AssetDefinition, value: number | null | undefined) {
  return value == null ? "—" : `${asset.pricePrefix ?? ""}${formatNumber(value, asset.digits ?? 2)}${asset.priceSuffix ?? ""}`;
}

function summarize(asset: AssetDefinition): AssetSummary {
  const row = verified(quoteRow(dailyReport, asset.symbol));
  const sector = Object.keys(dailyReport.daily_sector_performance ?? {}).find((name) => name.endsWith(`(${asset.symbol})`));
  const asYield = isYieldAsset(asset);
  const history = dailyReport.asset_history?.[asset.symbol];
  const spark = history && !history.error ? history.closes.slice(-22) : [];
  const change = asYield ? row?.abs_change ?? null : row?.pct_change ?? (sector ? dailyReport.daily_sector_performance[sector] : null) ?? null;
  return {
    slug: asset.slug,
    symbol: asset.symbol,
    name: asset.name,
    category: asset.category,
    logo: logoUrl(asset),
    price: row?.end_price ?? null,
    priceText: formatAssetPrice(asset, row?.end_price),
    change,
    changeText: asYield ? formatBpsFromPoints(change) : formatPct(change),
    tone: toneClass(change),
    spark,
    sparkTone: spark.length > 1 ? toneClass(spark.at(-1)! - spark[0]) : "",
  };
}

export const assetSummaries: AssetSummary[] = assetCatalog.map(summarize);

/** Biggest percent gainers and losers among assets with a verified move (yields excluded: bps are not comparable). */
export function topMovers(count = 3) {
  const ranked = assetSummaries
    .filter((summary) => summary.change != null && !isYieldAsset(assetCatalog.find((asset) => asset.slug === summary.slug)!))
    .sort((a, b) => b.change! - a.change!);
  return { gainers: ranked.slice(0, count).filter((s) => s.change! > 0), losers: ranked.slice(-count).reverse().filter((s) => s.change! < 0) };
}

/**
 * 52-week range from stored daily closes (not intraday extremes). `latest`, the
 * verified session close, replaces the stored last close so the marker sits on
 * the published number.
 */
export function yearRange(symbol: string, latest?: number | null) {
  const history = dailyReport.asset_history?.[symbol];
  const closes = history && !history.error ? history.closes.slice(-253) : [];
  if (closes.length < 20) return null;
  const window = latest != null && history?.as_of === dailyReport.session_date ? [...closes.slice(0, -1), latest] : latest != null ? [...closes.slice(1), latest] : closes;
  return { low: Math.min(...window), high: Math.max(...window), last: window.at(-1)!, sessions: window.length };
}

