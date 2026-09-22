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

- **Market scorecard:** S&P 500, Nasdaq Composite, Dow Jones, Russell 2000, VIX, 10-year Treasury yield, DXY, Bitcoin and Ethereum.
- **Sector leadership:** all 11 S&P sector ETFs ranked by session return, plus relative strength versus SPY over 1D, 5D and 1M for sectors and tracked large caps.
- **Market internals:** sectors advancing, equal weight versus cap weight (1D/5D/1M), sector ETFs above their 20/50/200-day averages, 20-session highs and lows, and a 20-session sector advance/decline line. Every measure names its tracked universe; exchange-wide NYSE/Nasdaq breadth is listed as not covered rather than approximated.
- **Rates and credit:** Cboe yield indexes for the session, the official U.S. Treasury par curve (including 2Y, 2s10s, 3M–10Y, 5s30s and real yields), actual ICE BofA credit spreads from FRED, and bond ETFs clearly labeled as price proxies.
- **Regime history:** 60 sessions of Constructive / Mixed / Defensive classifications. Days published in an archived issue are shown as published; other days are reconstructed with the same rule and labeled.
- **Verified catalysts:** Federal Reserve, BLS and BEA releases first, then an exact allowlist of reputable publishers. Every item has a source, link and timestamp, and none is presented as the cause of a move.
- **Market calendar:** U.S. economic releases (actual, consensus and previous as published), Treasury auctions, tracked earnings and NYSE market-structure dates for the current and next session, in Central Time.
- **Mega-cap and semiconductor leadership:** AAPL, MSFT, NVDA, AMZN, META, SNDK, AMD, INTC and MU.
- **Cross-asset context:** gold, crude oil, major global equity indexes, Bitcoin, Ethereum, Solana and XRP, each labeled with its own local session date.
- **Data health:** a freshness and status strip (Verified / Partial / Some feeds unavailable / Limited) and a per-source feed list on every issue.

## Daily workflow

- **Morning Tape (`/morning/`):** index futures with freshness and delay labels, overnight Asia and Europe, the official Treasury curve, the dollar, commodities, crypto, today's calendar, overnight catalysts and a short observed-only "What matters today".
- **Close Tape (`/`):** the end-of-session report.
- **Asset pages (`/assets/<slug>/`):** interactive 1D / 5D / 1M / 3M / YTD / 1Y charts with pointer, touch and keyboard inspection, session range, moving averages, tagged catalysts and recent archive sessions.
- **Archive (`/reports/`):** permanent dated issues with search by date, headline, sector or ticker, a regime filter, previous/next navigation and historical comparisons.
- **Watchlist:** up to 20 tracked assets stored only in the browser.
- **Delivery and sharing:** Discord posts for new issues only, RSS, an installable PWA that never serves stale market data offline, and permanent share links for key sections.
- **Keyboard:** press `?` on any page for shortcuts.

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
    ├─ adds calendar, catalysts, Treasury curve and credit spreads (failures are non-fatal and recorded)
    ├─ computes internals, relative strength and 60-session regime history
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

## Configuration

| Variable | Where | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Railway | Optional narrative rewording; the report falls back to deterministic copy without it |
| `GITHUB_TOKEN` | Railway | Commits generated artifacts |
| `GITHUB_BRANCH` | Railway | Branch the crons commit to (default `main`) |
| `DISCORD_WEBHOOK_URL` | Railway | Optional delivery channel |
| `DAILY_TAPE_DISABLED_FEEDS` | Railway | Optional comma-separated feed ids to skip |
| `PLAUSIBLE_DOMAIN` | GitHub repository variable | Optional, cookieless analytics |

No keys are needed for the calendar, catalyst, Treasury or FRED feeds.

More detail: [data providers](docs/DATA_PROVIDERS.md), [delivery](docs/DELIVERY.md), [analytics](docs/ANALYTICS.md).

## Development

```bash
python -m unittest -v          # fully offline; no test touches the network
npm run lint
npm run build:pages            # static export to ./out
python scripts/validate_export.py
```

## Data notes

Market data is sourced through `yfinance` and therefore depends on upstream availability and data quality. The generator applies sanity bounds, rejects rows from a different session than the report, stores unavailable values as null rather than zero, and records every source's status in the report. Those checks are not a guarantee that every upstream quote is error-free.

When Anthropic is enabled, narrative text is machine-generated from the report context. Important market information should still be verified against primary or institutional sources before it is used for financial decisions.

© 2026 coolxng. All rights reserved.
