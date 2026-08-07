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
| Build tooling | Vinext / Vite |
| Cloud tooling | Cloudflare Wrangler |
| Hosting | GitHub Pages |
| Automation | GitHub Actions |

## Local Setup

### Requirements

- Python 3.10+
- Node.js 22+
- npm

Clone the repository:

```bash
git clone https://github.com/coolxng/market-summary.git
cd market-summary
```

Install the Python dependency:

```bash
pip install yfinance
```

Install frontend dependencies:

```bash
npm install
```

### Optional: Enable AI Commentary

Set your Anthropic API key before generating the report.

macOS / Linux:

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

PowerShell:

```powershell
$env:ANTHROPIC_API_KEY="your-api-key"
```

The project will still run without an Anthropic API key using its fallback commentary mode.

## Generate a Market Report

Run:

```bash
python generate_report.py
```

This updates:

```text
report_snapshot.json
public/legacy-report.html
```

The snapshot contains the structured market data consumed by the main frontend.

## Run the Site Locally

```bash
npm run dev
```

## Build

Standard build:

```bash
npm run build
```

GitHub Pages static build:

```bash
npm run build:pages
```

## Tests

Run the full test pipeline:

```bash
npm test
```

This runs the Python report-generator tests followed by a frontend production build.

You can also run the Python tests independently:

```bash
python -m unittest -v
```

## Automation

GitHub Actions handles the daily report lifecycle.

The market-summary workflow runs on weekdays after the U.S. market close and:

1. Sets up Python and Node.js.
2. Installs `yfinance`.
3. Runs `generate_report.py`.
4. Runs the test suite.
5. Validates the generated market snapshot.
6. Builds the frontend.
7. Commits updated report artifacts when a new trading session exists.

A separate deployment workflow builds the static Next.js site and publishes it to GitHub Pages.

Market holidays are handled by the generator rather than the GitHub Actions cron schedule.

## Project Structure

```text
market-summary/
├── .github/
│   └── workflows/
│       ├── market-summary.yml
│       └── deploy-pages.yml
├── app/
│   └── page.tsx
├── public/
│   └── legacy-report.html
├── generate_report.py
├── report_snapshot.json
├── test_generate_report.py
├── package.json
├── next.config.ts
├── vite.config.ts
└── tsconfig.json
```

## Data Reliability

The generator includes several safeguards before publishing a report:

- completed-session detection
- previous-session comparison
- weekend handling
- U.S. market-holiday handling
- missing-data validation
- sanity bounds for major assets
- fallback tickers for selected commodities
- validation of core market datasets
- automated tests before generated artifacts are committed

These checks are intended to reduce the chance of publishing incomplete or obviously incorrect market data.

## Disclaimer

This project is for informational and educational purposes only.

Nothing generated by Market Summary should be considered financial, investment, trading, or legal advice. Market data may be delayed, incomplete, or inaccurate.

## Author

Built by [coolxng](https://github.com/coolxng).
