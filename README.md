<div align="center">

<img src="./public/favicon.svg" alt="The Daily Tape favicon" width="92" />

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

## Historical report archive

The Daily Tape keeps a permanent archive of completed trading sessions so past reports can be revisited, shared, and referenced later.

- **Latest live dashboard:** https://coolxng.github.io/market-summary/
- **Report archive:** https://coolxng.github.io/market-summary/reports/
- **Example archived session:** https://coolxng.github.io/market-summary/reports/2026-09-18/
- Every completed trading session gets its own permanent `/reports/YYYY-MM-DD/` page.
- Each archived session preserves both the rendered HTML report and its matching JSON snapshot.

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
public/legacy-report.html
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
