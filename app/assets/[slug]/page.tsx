import report from "../../../report_snapshot.json";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { assetBySlug, assetCatalog } from "../../lib/assets";
import AssetClient from "./AssetClient";
import { catalystsOf, verified, type DailyReport } from "../../lib/report";

const dailyReport = report as unknown as DailyReport;
const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/$/, "");

export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return assetCatalog.map((asset) => ({ slug: asset.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const asset = assetBySlug[slug];
  if (!asset) return {};
  const title = `${asset.name} Market Dashboard | The Daily Tape`;
  const description = `Price action, trend references, and source-linked market context for ${asset.name} (${asset.symbol}) inside The Daily Tape.`;
  return {
    title,
    description,
    alternates: { canonical: `${siteUrl}/assets/${slug}/` },
    openGraph: { title, description, url: `${siteUrl}/assets/${slug}/`, type: "website" },
  };
}

export default async function AssetPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const asset = assetBySlug[slug];
  if (!asset) notFound();

  const current = verified(dailyReport.market_data?.[asset.symbol] ?? dailyReport.mega_cap_data?.[asset.symbol]?.result);
  const session =
    dailyReport.session_charts?.[asset.symbol] ??
    dailyReport.mega_cap_data?.[asset.symbol]?.session_chart ??
    null;
  const history = dailyReport.asset_history?.[asset.symbol] ?? null;
  const headlines = (catalystsOf(dailyReport)?.items ?? []).filter((item) => (item.related_tickers ?? []).includes(asset.symbol));

  return (
    <AssetClient
      asset={asset}
      current={current}
      session={session}
      history={history}
      headlines={headlines}
    />
  );
}
