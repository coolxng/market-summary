# Market Summary

An automated daily market dashboard that turns completed U.S. trading-session data into a fast, scannable market recap.

**Live site:** [coolxng.github.io/market-summary](https://coolxng.github.io/market-summary/)

## Overview

Market Summary automatically collects market data after the U.S. close, validates it, generates a structured daily snapshot, and publishes the results as **The Daily Tape**.

The report is designed to answer three basic questions:

- **What moved?**
- **Why did it matter?**
- **What should I watch next?**

Instead of presenting raw quotes alone, the dashboard combines market prices, intraday charts, sector breadth, mega-cap performance, global markets, crypto, rates, commodities, and generated market commentary in one report.

## What It Tracks

### Major U.S. Markets

- S&P 500
- Nasdaq Composite
- Dow Jones Industrial Average
- Russell 2000
- VIX
- 10-Year Treasury Yield
- U.S. Dollar Index

### Mega-Cap & Semiconductor Stocks

Includes tracked names such as:

- Apple
- Microsoft
- Nvidia
- Amazon
- Meta
- AMD
- Intel
- Micron
- SanDisk

### Global Markets

- Nikkei 225
- Euro Stoxx 50
- FTSE 100
- Hang Seng

### Crypto

- Bitcoin
- Ethereum
- Solana
- XRP

### Other Market Data

- Gold
- Crude oil
- Treasury yields
- U.S. dollar
- Sector performance
- Market breadth
- SPY vs. equal-weight RSP performance

## How It Works

The project has two main parts.

### 1. Market Data Generator

`generate_report.py` handles the daily data pipeline.

It:

1. Determines the latest completed U.S. trading session.
2. Accounts for weekends and market holidays.
3. Fetches market data using `yfinance`.
4. Checks prices against sanity bounds to catch obviously invalid data.
5. Builds intraday and daily market datasets.
6. Calculates sector performance and market breadth.
7. Generates market commentary.
8. Writes the resulting structured dataset to `report_snapshot.json`.
9. Generates a standalone legacy HTML report at `public/legacy-report.html`.

If no new completed market session exists, the generator avoids unnecessarily rewriting the report.

### 2. The Daily Tape Frontend

The main interface is built with:

- Next.js
- React
- TypeScript

The frontend reads directly from `report_snapshot.json` and turns the generated data into a data-dense market dashboard with:

- index cards
- intraday sparklines
- sector rankings
- breadth indicators
- mega-cap tracking
- macro data
- crypto data
- market commentary
- next-session watch items
- light and dark themes

## AI Commentary

The generator supports Anthropic-powered narrative analysis through:

```text
ANTHROPIC_API_KEY
```

When an Anthropic API key is available, the report can generate commentary for areas such as:

- mega-cap stocks
- crypto
- global markets
- daily market takeaways
- next-session catalysts
- macro risks
- Fed and rates
- earnings

If no API key is configured, the generator falls back to deterministic commentary so the report can still be generated.

## Tech Stack

| Layer | Technology |
|---|---|
| Market data | Python + yfinance |
| Analysis pipeline | Python |
| AI commentary | Anthropic API |
| Frontend | Next.js 16 |
| UI | React 19 |
| Language | TypeScript |
| Hosting | GitHub Pages |
| Scheduling | Railway Cron |
| CI / deployment | GitHub Actions |

