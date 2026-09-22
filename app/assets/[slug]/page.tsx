import report from "../../../report_snapshot.json";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { assetBySlug, assetCatalog } from "../../lib/assets";
import AssetClient from "./AssetClient";

type MarketDatum = {
  end_price: number;
  pct_change: number;
  day_high?: number;
  day_low?: number;
  prev_close?: number;
};

type ReportShape = {
  market_data?: Record<string, MarketDatum>;
  session_charts?: Record<string, { times: string[]; closes: number[]; source?: string }>;
  mega_cap_data?: Record<string, { result?: MarketDatum; session_chart?: { times: string[]; closes: number[]; source?: string } }>;
  asset_history?: Record<string, {
    dates: string[];
    closes: number[];
    returns?: Record<string, number | null>;
    moving_averages?: Record<string, number | null>;
    above_moving_average?: Record<string, boolean | null>;
    source?: string;
    as_of?: string | null;
    error?: string | null;
  }>;
  market_headlines?: { items?: Array<{ title: string; url: string; publisher: string; published_at?: number | null; related_tickers?: string[] }> };
};

const dailyReport = report as ReportShape;
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

  const current =
    dailyReport.market_data?.[asset.symbol] ??
    dailyReport.mega_cap_data?.[asset.symbol]?.result ??
    null;
  const session =
    dailyReport.session_charts?.[asset.symbol] ??
    dailyReport.mega_cap_data?.[asset.symbol]?.session_chart ??
    null;
  const history = dailyReport.asset_history?.[asset.symbol] ?? null;
  const headlines = (dailyReport.market_headlines?.items ?? []).filter((item) => {
    const related = item.related_tickers ?? [];
    return related.includes(asset.symbol);
  });

  return (
    <AssetClient
      asset={asset}
      current={current}
      session={session}
      history={history}
      headlines={headlines}
      archiveHref="../../reports/"
    />
  );
}
