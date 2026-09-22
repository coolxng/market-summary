# Data providers

The Daily Tape separates what it publishes into three kinds of information:

| Kind | Meaning | Where it comes from |
| --- | --- | --- |
| **Observed** | Prices, returns and ratios computed from market data | Yahoo Finance via `yfinance` (Stooq fallback for core indexes) |
| **Verified catalyst** | An external development with a publisher, link and timestamp | Official RSS feeds and allowlisted news publishers |
| **Interpretation** | Clearly labeled reading of observed data | Deterministic evidence cards, optionally reworded by Claude under strict validation |

Catalysts and calendar items are always shown as context. The narrative layer is not allowed to attribute a price move to them (see `validate_editorial_prose` in `generate_report.py`).

## Feed contract

Every calendar and catalyst provider in `data_providers.py` returns a normalized `FeedResult`:

```json
{
  "id": "fair_economy_economic",
  "name": "Forex Factory Economic Calendar",
  "source_url": "https://www.forexfactory.com/calendar",
  "status": "ok | empty | unavailable | disabled",
  "as_of": "2026-09-22T20:31:04+00:00",
  "items": [],
  "error": null
}
```

- A provider failure never raises into report generation. The feed is marked `unavailable` and its items are omitted.
- Missing values stay `null`. Nothing is converted to zero, estimated, or filled with placeholder text.
- Feed status (without items) is stored in the report so the page can show which sources were checked.

## Calendar providers (`build_market_calendar`)

Window: the current trading session (if the anchor date trades) plus the next NYSE trading session, from `trading_calendar.session_window`.

| Feed id | Source | Notes |
| --- | --- | --- |
| `fair_economy_economic` | Forex Factory / Fair Economy weekly JSON | USD rows only. The provider reads the explicit ISO-8601 timestamp and UTC offset from each event, converts that timestamp to Central Time, and derives the displayed date from the converted timestamp. This avoids guessing a timezone from a clock-only field or stamping rows onto the requested date. This-week and next-week feeds are merged and deduplicated; source impact, forecast and previous values are copied as published. |
| `treasury_auctions` | U.S. Treasury Fiscal Data `upcoming_auctions` | Auction date, term, type, offering size and CUSIP. The dataset has no auction close time, so the time is shown as not published. |
| `yahoo_earnings` | Yahoo Finance company calendar | Tracked mega-cap and semiconductor names only. A two-date answer is labeled as an estimated window. |
| `market_structure` | `trading_calendar.py` rules | NYSE holidays, 1:00 PM ET early closes and third-Friday options expiration. Items are labeled "Rule-based" because rules cannot anticipate unscheduled closures. |

Category labels (Inflation, Employment, and so on) are keyword classifications of the event title. They are not importance scores.

## Catalyst providers (`build_verified_catalysts`)

Window: from 4:00 PM ET on the previous session to generation time (close report), or from the previous close to generation time (Morning Tape). Items without a timestamp are dropped because they cannot be placed in the window.

| Feed id | Source | Notes |
| --- | --- | --- |
| `fed_monetary` | Federal Reserve monetary policy press releases RSS | Primary official feed. |
| `fed_speeches` | Federal Reserve speeches RSS | Primary official feed. |
| `bls_releases` | U.S. Bureau of Labor Statistics RSS | The aggregate latest-releases feed is primary. If that endpoint is blocked or unavailable, major release feeds (Employment Situation, CPI, PPI and JOLTS) are queried as fallbacks and deduplicated by source URL. |
| `bea_releases` | U.S. Bureau of Economic Analysis releases RSS | Primary official feed. |
| `yahoo_news` | Yahoo Finance news search, filtered to an exact publisher allowlist (Reuters, Bloomberg, CNBC, AP, WSJ, Dow Jones, FT, MarketWatch, Barron's, Yahoo Finance) | Reputable-news fallback when official feeds do not fill the catalyst window. |

Official items are listed first. At most six items are published. "Tagged by source" tickers come from the publisher's own metadata; The Daily Tape does not infer affected assets.

## Official rates and credit (`official_rates.py`)

| Feed id | Source | Notes |
| --- | --- | --- |
| `treasury_curve` | U.S. Treasury daily par yield curve and real yield curve | The documented Treasury XML feed is primary; the CSV endpoint is retained as a fallback. Latest row on or before the anchor date, the prior row for day-over-day changes, and 2s10s, 3M–10Y and 5s30s spreads in basis points are retained. Treasury publishes once a day in the late afternoon, so the close report often shows the prior day's curve. The page always prints the curve's own date. |
| `fred_credit` | FRED `fredgraph.csv` for ICE BofA US High Yield OAS (`BAMLH0A0HYM2`) and US Corporate OAS (`BAMLC0A0CM`) | Actual option-adjusted credit spreads, converted to basis points. FRED's ICE series lag by about a day and are labeled with their own date. |

The Morning Tape uses the Treasury curve as its official 2-year and 10-year reference. The CBOT 2-year yield futures quote is shown separately and labeled as a proxy.

## Configuration

| Variable | Purpose |
| --- | --- |
| `DAILY_TAPE_DISABLED_FEEDS` | Comma-separated feed ids to skip, for example `yahoo_news,bls_releases,treasury_curve,fred_credit`. Disabled feeds are reported as disabled, not unavailable. |

No API keys are required for the current providers. None are committed.

## Adding a provider

1. Write a function that returns `feed_result(...)` through the `_run` helper so failures are contained.
2. Normalize items to the calendar or catalyst item shape used in `app/lib/report.ts` (`CalendarItem` or `Catalyst`).
3. Add it to the provider list in `build_market_calendar` or `build_verified_catalysts`.
4. Add unit tests that mock `http_get`; the test suite must never touch the network because `railway_cron.py` runs it before publishing.

A paid economic calendar with provider-assigned importance, or a licensed newswire, would slot in the same way. Read the key from an environment variable in the provider function and return a `disabled` feed when the key is absent.

## Market data

`generate_report.fetch_daily_data` uses Yahoo Finance first and Stooq as a fallback for core indexes and U.S. tickers. Rows that cannot be fetched are stored with `null` prices and an `error`. Core indexes still fail the run through `validate_core_datasets`, so a report is never published without them.

`build_data_quality` checks every row against the report session. Overseas indexes and crypto run on other calendars, so they are compared with the previous U.S. session instead. When their latest local session differs from the report date, the page labels the row with that date.
