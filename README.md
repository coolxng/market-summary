<div align="center">

<img src="./public/logo.png" alt="The Daily Tape favicon" width="92" />

# The Daily Tape

**Automated market-close intelligence for the latest completed U.S. trading session.**

[Open the live dashboard](https://coolxng.github.io/market-summary/)

[![Deploy GitHub Pages](https://github.com/coolxng/market-summary/actions/workflows/deploy-pages.yml/badge.svg)](https://github.com/coolxng/market-summary/actions/workflows/deploy-pages.yml)

</div>

<p align="center">
  <img src="./assets/screenshots/The-daily-tape.png" alt="The Daily Tape market overview, regime monitor, and scorecard" width="900" />
</p>

## Overview

**Market Summary** is an automated data pipeline and static web dashboard that turns the latest completed U.S. trading session into a compact daily report called **The Daily Tape**.

Instead of stopping at raw quotes, it combines index performance, market breadth, sector leadership, mega-cap and semiconductor moves, rates, the dollar, commodities, global equities, crypto, intraday price paths, and market commentary in one report.

It is built for fast end-of-session review: **what moved, where leadership came from, how broad the move was, and what matters next.**

| Area | Implementation |
| --- | --- |
| Market data | Yahoo Finance through `yfinance` |
| Report generation | Python |
| Frontend | Next.js 16, React 19, TypeScript |
| Production automation | Railway cron job |
| Static deployment | GitHub Pages |
| Narrative layer | Claude Sonnet 5, with deterministic fallback copy in the generator |

## What it tracks

- **Market scorecard:** S&P 500, Nasdaq Composite, Dow Jones, Russell 2000, VIX, 10-year Treasury yield, and DXY.
- **Sector leadership:** all 11 S&P sector ETFs, ranked by session return.
- **Breadth:** cap-weighted vs. equal-weight S&P performance, advancing sectors, positive-sector share, and participation context.
- **Mega-cap and semiconductor leadership:** AAPL, MSFT, NVDA, AMZN, META, SNDK, AMD, INTC, and MU.
- **Cross-asset context:** gold, crude oil, major global equity indexes, Bitcoin, Ethereum, Solana, and XRP.
- **Session narrative:** a one-line read, regime monitor, market/leadership/internals takeaways, macro context, and next-session watch items.
- **Verified session paths:** intraday charts are tied to the completed regular-hours session when the underlying data is available.
- **Historical archive:** every completed trading session gets its own permanent `/reports/YYYY-MM-DD/` page.

## Daily workflow

The roadmap build expands The Daily Tape from a single close report into a repeat-use market workflow:

- **Morning Tape:** futures, overnight/global markets, rates, dollar, commodities, crypto, upcoming economic events, tracked earnings, and source-linked headlines.
- **Close Tape:** the existing end-of-session report, enriched with catalysts/calendar context, data health, rates and credit, trend participation, relative strength, and a local watchlist.
- **Asset dashboards:** interactive 1D / 5D / 1M / 3M / YTD / 1Y price paths with hover inspection, moving averages, watchlist controls, and source-linked context.
- **Search:** fast lookup across tracked assets and archived sessions.
- **Delivery:** RSS plus installable PWA support so the Tape can live outside a browser tab.
- **Research archive:** permanent dated reports with previous/next navigation and regime-history context.

### Production services

The close and morning publications are intentionally separate Railway cron services:

- `railway.toml` runs the Close Tape in both possible UTC slots and `railway_cron.py` keeps only the **3 PM America/Chicago** slot. This handles daylight-saving changes automatically.
- `railway.morning.toml` runs the Morning Tape in both possible UTC slots and `morning_cron.py` keeps only the **7 AM America/Chicago** slot.
- Manual runs can bypass the local-time guards with `MARKET_SUMMARY_FORCE=1` or `MORNING_TAPE_FORCE=1`.
- Both publishers commit generated JSON artifacts back to the configured `GITHUB_BRANCH`.

## Historical report archive

The Daily Tape keeps a permanent archive of completed trading sessions so past reports can be revisited, shared, and referenced later.

- **Latest live dashboard:** https://coolxng.github.io/market-summary/
- **Report archive:** https://coolxng.github.io/market-summary/reports/
- **Example archived session:** https://coolxng.github.io/market-summary/reports/2026-09-18/
- Every completed trading session gets its own permanent `/reports/YYYY-MM-DD/` page.
- Each archived session preserves a JSON snapshot that the current Next.js report UI renders.

## Product tour

### Market overview

The opening view condenses the session into one headline, a regime monitor, key takeaways, and the primary index scorecard. It is designed to answer the broad market question before the reader moves into individual sectors or names.

### Sector leadership

<p align="center">
  <img src="./assets/screenshots/Where-the-tape.png" alt="The Daily Tape sector leadership ranking with breadth checks" width="900" />
</p>

All 11 sector ETFs are ranked by session return and paired with breadth checks. That makes it easier to distinguish a broad move from an index move carried by a small group of large stocks.

### The Leadership Engine

<p align="center">
  <img src="./assets/screenshots/The-Leadership-engine.png" alt="The Daily Tape sector leadership ranking with breadth checks" width="900" />
</p>

Shows Stock prices at close.

## How it works

```text
Railway cron
    │
    ▼
railway_cron.py
    │
    ▼
generate_report.py
    ├─ resolves the latest completed U.S. session
    ├─ downloads market data with yfinance
    ├─ validates core prices and sanity bounds
    ├─ builds index, sector, breadth, macro, crypto, and intraday data
    └─ generates market commentary
    │
    ▼
report_snapshot.json
public/reports/YYYY-MM-DD/report.json
    │
    ▼
validated artifacts are committed to main
    │
    ▼
GitHub Pages workflow
    │
    ▼
Next.js static export → live dashboard
```

## Data notes

Market data is sourced through `yfinance` and therefore depends on upstream availability and data quality. The generator includes sanity bounds and artifact validation to catch obvious failures, but those checks are not a guarantee that every upstream quote is error-free.

When Anthropic is enabled, narrative text is machine-generated from the report context. Important market information should still be verified against primary or institutional sources before it is used for financial decisions.

© 2026 coolxng. All rights reserved.
