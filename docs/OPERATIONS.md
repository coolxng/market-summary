# Operations

Owner-facing notes for running The Daily Tape. The product-facing overview lives in the [README](../README.md).

## Production services

The close and morning publications are intentionally separate Railway cron services. Railway cron schedules are in UTC, so each service runs in every UTC slot that can map to its local publish time, and a local-time guard in Python keeps only the right one. This handles daylight-saving changes automatically.

- `railway.toml` runs the Close Tape every 15 minutes from 20:00 to 22:45 UTC on weekdays (`*/15 20-22 * * 1-5`). `railway_cron.py` only proceeds inside the **3:25 to 4:29 PM America/Chicago** publish window, so the first attempt is at 3:30 PM CT and later slots act as retries. Once the remote `report_snapshot.json` already has today's session date, retries exit without API or market-data work.
- `railway.morning.toml` runs the Morning Tape at 12:45 and 13:45 UTC on weekdays (`45 12,13 * * 1-5`). `morning_cron.py` keeps only the slot that falls in the **7 AM America/Chicago** hour, so it publishes at 7:45 AM CT.
- Manual runs can bypass the local-time guards with `MARKET_SUMMARY_FORCE=1` or `MORNING_TAPE_FORCE=1`.
- For a deliberate live-provider validation of an already-published Close Tape session, temporarily pair `MARKET_SUMMARY_FORCE=1` with `MARKET_SUMMARY_REGENERATE=1`. Remove the regeneration flag after the test.
- `MARKET_SUMMARY_PAUSED=1` makes the Close Tape service exit without API usage.
- Both publishers commit generated JSON artifacts back to the configured `GITHUB_BRANCH`. The Close Tape writes `report_snapshot.json` and `public/reports/YYYY-MM-DD/report.json`; the Morning Tape writes `morning_snapshot.json` and `public/morning/latest.json`. Those paths are excluded from Railway's build watch patterns so artifact commits do not trigger rebuilds.

## Configuration

| Variable | Where | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Railway | Required by the Close Tape service: `railway_cron.py` exits if it is missing. The generator can still fall back to deterministic copy when the narrative model call fails. The Morning Tape service does not need it |
| `GITHUB_TOKEN` | Railway | Commits generated artifacts |
| `GITHUB_BRANCH` | Railway | Branch the crons commit to (default `main`) |
| `DISCORD_WEBHOOK_URL` | Railway | Optional delivery channel |
| `DAILY_TAPE_CONTACT_EMAIL` | Railway | Contact email added to the User-Agent for bls.gov only; BLS returns 403 without one. Kept out of the repository |
| `DAILY_TAPE_DISABLED_FEEDS` | Railway | Optional comma-separated feed ids to skip |
| `MARKET_SUMMARY_REGENERATE` | Railway | Manual-only override to rebuild the latest completed Close Tape session; remove after validation |
| `PLAUSIBLE_DOMAIN` | GitHub repository variable | Optional, cookieless analytics |

No keys are needed for the calendar, catalyst, Treasury or FRED feeds.

## Development

```bash
python -m unittest -v          # fully offline; no test touches the network
npm run lint
npm run build:pages            # static export to ./out
python scripts/validate_export.py
```

## Screenshots

`scripts/capture_screenshots.mjs` recaptures the README screenshots from the live site with headless Chromium. It captures every shot twice, as `<name>-light.png` and `<name>-dark.png`, by setting Playwright's `colorScheme` and the site's `daily-tape-theme` localStorage key (`paper` or `ink`), and fails if a page renders in the wrong theme. The README shows the pair with `<picture>`, so GitHub serves the one that matches the reader's theme. Playwright and Sharp are installed outside the repo so `package.json` and `package-lock.json` stay untouched:

```bash
mkdir -p /tmp/daily-tape-shots && cd /tmp/daily-tape-shots
npm init -y && npm i playwright sharp && npx playwright install chromium
cd /path/to/market-summary
NODE_PATH=/tmp/daily-tape-shots/node_modules node scripts/capture_screenshots.mjs
```

The mobile shot is one iPhone 14 screen (390×797 CSS px at 3×, below a drawn 47pt status bar), framed with rounded corners, a bezel and a Dynamic Island. Set `ONLY=morning-tape,asset-page` to capture a subset, or `THEMES=dark` to capture one theme. Output goes to `assets/screenshots/`, resized to at most 1800px wide. Inspect every image before committing: retake any shot that shows loading states, a "Limited" or "Some feeds unavailable" status, or an unpublished Morning Tape.

## More documentation

- [Data providers](DATA_PROVIDERS.md)
- [Delivery](DELIVERY.md)
- [Analytics](ANALYTICS.md)
