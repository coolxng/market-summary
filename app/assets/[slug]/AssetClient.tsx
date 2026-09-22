"use client";

import { useEffect, useMemo, useState } from "react";
import type { AssetDefinition } from "../../lib/assets";
import styles from "./asset.module.css";

type PointSeries = { dates: string[]; closes: number[] };
type SessionSeries = { times: string[]; closes: number[]; source?: string };
type History = PointSeries & {
  returns?: Record<string, number | null>;
  moving_averages?: Record<string, number | null>;
  above_moving_average?: Record<string, boolean | null>;
  source?: string;
  as_of?: string | null;
  error?: string | null;
};
type Headline = {
  title: string;
  url: string;
  publisher: string;
  published_at?: number | null;
  related_tickers?: string[];
};

const ranges = ["1D", "5D", "1M", "3M", "YTD", "1Y"] as const;
type Range = typeof ranges[number];

function formatNumber(value: number, digits = 2) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function formatPct(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function sliceRange(series: PointSeries, range: Exclude<Range, "1D">) {
  if (!series.closes.length) return series;
  const sessions: Record<Exclude<Range, "1D" | "YTD">, number> = {
    "5D": 6,
    "1M": 22,
    "3M": 64,
    "1Y": 253,
  };
  if (range === "YTD") {
    const year = series.dates.at(-1)?.slice(0, 4);
    const start = series.dates.findIndex((date) => date.startsWith(`${year}-`));
    return start >= 0
      ? { dates: series.dates.slice(start), closes: series.closes.slice(start) }
      : series;
  }
  const count = sessions[range];
  return { dates: series.dates.slice(-count), closes: series.closes.slice(-count) };
}

function Chart({ labels, values }: { labels: string[]; values: number[] }) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  if (values.length < 2) return <div className={styles.emptyChart}>Longer-range history will appear after the next data refresh.</div>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const coordinates = values.map((value, index) => ({
    x: (index / (values.length - 1)) * 100,
    y: 90 - ((value - min) / span) * 78,
  }));
  const points = coordinates.map(({ x, y }) => `${x},${y}`).join(" ");
  const first = labels[0];
  const middle = labels[Math.floor(labels.length / 2)];
  const last = labels.at(-1);
  const active = activeIndex == null ? null : {
    index: activeIndex,
    value: values[activeIndex],
    label: labels[activeIndex] ?? "",
    ...coordinates[activeIndex],
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    setActiveIndex(Math.round(ratio * (values.length - 1)));
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Home") {
      setActiveIndex(0);
      return;
    }
    if (event.key === "End") {
      setActiveIndex(values.length - 1);
      return;
    }
    const current = activeIndex ?? values.length - 1;
    setActiveIndex(Math.min(values.length - 1, Math.max(0, current + (event.key === "ArrowRight" ? 1 : -1))));
  };

  return (
    <div
      className={styles.chartWrap}
      onPointerMove={handlePointerMove}
      onPointerLeave={() => setActiveIndex(null)}
      onFocus={() => setActiveIndex((current) => current ?? values.length - 1)}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="group"
      aria-label="Interactive price chart. Use left and right arrow keys to inspect points."
    >
      <div className={styles.chartCanvas}>
        <svg className={styles.chart} viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Interactive price chart">
          <polyline points={points} fill="none" stroke="var(--accent)" strokeWidth="2.2" vectorEffect="non-scaling-stroke" />
          {active && (
            <>
              <line x1={active.x} x2={active.x} y1="5" y2="95" className={styles.crosshair} vectorEffect="non-scaling-stroke" />
              <circle cx={active.x} cy={active.y} r="1.5" className={styles.hoverDot} vectorEffect="non-scaling-stroke" />
            </>
          )}
        </svg>
        {active && (
          <div
            className={styles.chartTooltip}
            style={{ left: `${Math.min(92, Math.max(8, active.x))}%` }}
            aria-live="polite"
          >
            <span>{active.label}</span>
            <strong>{formatNumber(active.value, Math.abs(active.value) < 10 ? 4 : 2)}</strong>
          </div>
        )}
      </div>
      <div className={styles.axis}><span>{first}</span><span>{middle}</span><span>{last}</span></div>
      <button className={styles.dataToggle} type="button" onClick={() => setShowTable((value) => !value)} aria-expanded={showTable}>
        {showTable ? "Hide chart data" : "View chart data"}
      </button>
      {showTable && (
        <div className={styles.dataTableWrap}>
          <table className={styles.dataTable}>
            <caption>Price chart data</caption>
            <thead><tr><th scope="col">Time / date</th><th scope="col">Value</th></tr></thead>
            <tbody>
              {values.map((value, index) => (
                <tr key={`${labels[index] ?? index}-${index}`}>
                  <td>{labels[index] ?? "—"}</td>
                  <td>{formatNumber(value, Math.abs(value) < 10 ? 4 : 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function AssetClient({
  asset,
  current,
  session,
  history,
  headlines,
  archiveHref,
}: {
  asset: AssetDefinition;
  current: { end_price: number; pct_change: number; day_high?: number; day_low?: number; prev_close?: number } | null;
  session: SessionSeries | null;
  history: History | null;
  headlines: Headline[];
  archiveHref: string;
}) {
  const [theme, setTheme] = useState<"paper" | "ink">("paper");
  const [range, setRange] = useState<Range>("1D");
  const [watched, setWatched] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const saved = window.localStorage.getItem("daily-tape-theme");
      if (saved === "ink") setTheme("ink");
      const watchlist = JSON.parse(window.localStorage.getItem("daily-tape-watchlist") || "[]") as string[];
      setWatched(watchlist.includes(asset.slug));
    });
    return () => window.cancelAnimationFrame(frame);
  }, [asset.slug]);

  const toggleTheme = () => {
    const next = theme === "paper" ? "ink" : "paper";
    document.documentElement.dataset.theme = next;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", next === "ink" ? "#080808" : "#f3f0e7");
    const favicon = document.getElementById("site-favicon") as HTMLLinkElement | null;
    if (favicon) favicon.href = new URL(next === "ink" ? "favicon-dark.svg" : "favicon-light.svg", favicon.href).href;
    window.localStorage.setItem("daily-tape-theme", next);
    setTheme(next);
  };

  const toggleWatch = () => {
    const currentList = JSON.parse(window.localStorage.getItem("daily-tape-watchlist") || "[]") as string[];
    const next = currentList.includes(asset.slug)
      ? currentList.filter((slug) => slug !== asset.slug)
      : [...currentList, asset.slug];
    window.localStorage.setItem("daily-tape-watchlist", JSON.stringify(next));
    setWatched(next.includes(asset.slug));
  };

  const chartData = useMemo(() => {
    if (range === "1D") {
      return {
        labels: session?.times ?? [],
        values: session?.closes ?? [],
      };
    }
    const sliced = sliceRange(history ?? { dates: [], closes: [] }, range);
    return { labels: sliced.dates, values: sliced.closes };
  }, [history, range, session]);

  const rangeReturn = range === "1D"
    ? current?.pct_change ?? null
    : chartData.values.length >= 2
      ? ((chartData.values.at(-1)! - chartData.values[0]) / chartData.values[0]) * 100
      : null;
  const positive = (rangeReturn ?? current?.pct_change ?? 0) >= 0;

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="../../" aria-label="The Daily Tape home">
          <span className="brand-mark" style={{ backgroundImage: 'url("https://coolxng.github.io/market-summary/logo.png")' }} />
          <span>THE DAILY TAPE</span>
        </a>
        <nav aria-label="Asset navigation">
          <a href="../../">Current report</a>
          <a href="../../morning/">Morning</a>
          <a href={archiveHref}>Archive</a>
          <a href="../../search/">Search</a>
        </nav>
        <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
          <span className="theme-toggle__icon" aria-hidden="true">{theme === "paper" ? "◐" : "◑"}</span>
          <span className="theme-toggle__label">{theme === "paper" ? "Ink" : "Paper"}</span>
        </button>
      </header>

      <div className={styles.page}>
        <section className={styles.hero}>
          <p className={styles.kicker}>{asset.category.toUpperCase()} / {asset.symbol}</p>
          <div className={styles.heroGrid}>
            <div>
              <h1>{asset.name}</h1>
              <p className={styles.sub}>Tracked inside The Daily Tape. Price history, trend references, and source-linked context in one view.</p>
            </div>
            <div className={styles.quote}>
              <span>LATEST CLOSE</span>
              <strong>{current ? `${asset.pricePrefix ?? ""}${formatNumber(current.end_price, asset.digits ?? 2)}${asset.priceSuffix ?? ""}` : "—"}</strong>
              <b className={positive ? "positive" : "negative"}>{formatPct(rangeReturn ?? current?.pct_change)}</b>
              <button onClick={toggleWatch}>{watched ? "✓ Watching" : "+ Watch"}</button>
            </div>
          </div>
        </section>

        <section className={styles.chartSection}>
          <div className={styles.rangeBar}>
            <div><span>PRICE PATH</span><strong>{formatPct(rangeReturn)}</strong></div>
            <div className={styles.rangeButtons}>
              {ranges.map((item) => <button key={item} className={range === item ? styles.active : ""} onClick={() => setRange(item)}>{item}</button>)}
            </div>
          </div>
          <Chart labels={chartData.labels} values={chartData.values} />
        </section>

        <section className={styles.performance} aria-label="Multi-period performance">
          {[
            ["1D", current?.pct_change ?? null],
            ["5D", history?.returns?.["5d"] ?? null],
            ["1M", history?.returns?.["1m"] ?? null],
            ["3M", history?.returns?.["3m"] ?? null],
            ["YTD", history?.returns?.["ytd"] ?? null],
            ["1Y", history?.returns?.["1y"] ?? null],
          ].map(([label, value]) => {
            const numeric = typeof value === "number" ? value : null;
            return <div key={label as string}><span>{label}</span><strong className={numeric == null ? "" : numeric >= 0 ? "positive" : "negative"}>{formatPct(numeric)}</strong></div>;
          })}
        </section>

        <section className={styles.stats}>
          <div><span>DAY LOW</span><strong>{current?.day_low ? formatNumber(current.day_low, asset.digits ?? 2) : "—"}</strong></div>
          <div><span>DAY HIGH</span><strong>{current?.day_high ? formatNumber(current.day_high, asset.digits ?? 2) : "—"}</strong></div>
          <div><span>20D AVG</span><strong>{history?.moving_averages?.["20d"] ? formatNumber(history.moving_averages["20d"]!, asset.digits ?? 2) : "—"}</strong></div>
          <div><span>50D AVG</span><strong>{history?.moving_averages?.["50d"] ? formatNumber(history.moving_averages["50d"]!, asset.digits ?? 2) : "—"}</strong></div>
          <div><span>200D AVG</span><strong>{history?.moving_averages?.["200d"] ? formatNumber(history.moving_averages["200d"]!, asset.digits ?? 2) : "—"}</strong></div>
        </section>

        <section className={styles.context}>
          <div className={styles.sectionHeading}>
            <div><p className={styles.kicker}>VERIFIED DEVELOPMENTS</p><h2>Relevant source-linked context</h2></div>
            <p>Only stored headlines explicitly tagged to this asset are shown. They remain context, not automatic explanations for the price move.</p>
          </div>
          {headlines.length ? (
            <div className={styles.newsList}>
              {headlines.slice(0, 6).map((item) => (
                <a href={item.url} target="_blank" rel="noreferrer" key={item.url}>
                  <span>{item.publisher}</span>
                  <strong>{item.title}</strong>
                  <b>Open source ↗</b>
                </a>
              ))}
            </div>
          ) : <p className={styles.empty}>No source-linked headlines are stored for this asset yet.</p>}
        </section>

        <aside className={styles.sourceNote}>
          <div><span>DATA SOURCE</span><strong>{history?.source ?? "Yahoo Finance via yfinance"}</strong></div>
          <p>Latest close and daily move come from the Daily Tape snapshot. Longer-range history is stored at report generation time so this page does not depend on a live browser-side finance API.</p>
          <span>{history?.as_of ? `HISTORY THROUGH ${history.as_of}` : "HISTORY PENDING NEXT REFRESH"}</span>
        </aside>
      </div>
    </main>
  );
}
