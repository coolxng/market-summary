import { assetSummaries } from "../lib/assetSummary";
import { archivedReports, reportHeadline } from "../lib/archive";
import { formatSessionDate } from "../lib/format";
import type { SearchIndex } from "../components/HeaderSearch";

export const dynamic = "force-static";

/**
 * Compact index behind the masthead search suggestions. Served as one static
 * file so the header only downloads it the first time someone uses the bar,
 * instead of every page carrying the full asset and archive list.
 */
export function GET() {
  const index: SearchIndex = {
    assets: assetSummaries.map(({ slug, symbol, name, category, logo, priceText, changeText, tone }) => ({
      slug, symbol, name, category, logo, priceText, changeText, tone,
    })),
    reports: archivedReports()
      .map(({ date, report }) => ({ date, displayDate: formatSessionDate(date), headline: reportHeadline(report) }))
      .reverse(),
  };
  return Response.json(index);
}
