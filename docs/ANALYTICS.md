# Analytics

The Daily Tape ships without analytics. Nothing is loaded and no events are sent unless a provider is configured at build time.

## Provider

Hooks exist for [Plausible](https://plausible.io/), which is cookieless and does not collect personal data. No account or site ID is committed.

| Setting | Where | Purpose |
| --- | --- | --- |
| `PLAUSIBLE_DOMAIN` | GitHub repository **variable** (Settings → Secrets and variables → Actions → Variables) | Passed to the Pages build as `NEXT_PUBLIC_PLAUSIBLE_DOMAIN`, for example `coolxng.github.io/market-summary` |
| `NEXT_PUBLIC_PLAUSIBLE_SRC` | Optional build env | Script URL for a self-hosted Plausible instance |

When the variable is empty, the layout renders no script and `track()` does nothing.

## Events

| Event | Props | Trigger |
| --- | --- | --- |
| `Archive opened` | none | `/reports/` loads |
| `Archived session opened` | `session` (date) | `/reports/YYYY-MM-DD/` loads |
| `Asset page opened` | `asset` (slug) | `/assets/<slug>/` loads |
| `Morning Tape opened` | none | `/morning/` loads |
| `Watchlist updated` | `size` (count only) | Add or remove on the watchlist |
| `Calendar source click` | `kind`, `host` | Source link in the market calendar |
| `Outbound source click` | `kind`, `host` | Catalyst, feed-health, credit or Treasury source links |

Page views are counted by the provider script itself.

## Rules

- Never send watchlist contents, search text, or anything a reader typed.
- Props are limited to dates, asset slugs, counts, link categories and hostnames.
- New events go through `app/lib/analytics.ts` so the no-provider path stays a no-op.
