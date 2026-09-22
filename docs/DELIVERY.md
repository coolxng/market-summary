# Delivery

`delivery.py` turns a published artifact into a normalized `Publication` and hands it to every configured channel.

## When messages are sent

| Event | Close Tape (`railway_cron.py`) | Morning Tape (`morning_cron.py`) |
| --- | --- | --- |
| New artifact committed | One message with session, headline, S&P 500 move, sector breadth, regime, data status and the permanent archive link | One message with the edition date, S&P futures move, quote coverage and the first "What matters today" line |
| Run finds nothing new | Nothing is posted | Nothing is posted |
| Run fails | One failure message; configured secret values are redacted from the error text | Same |

Earlier builds posted a "checked, nothing new" message on every quiet run. That is intentionally gone.

## Channels

| Channel | Status | Configuration |
| --- | --- | --- |
| Discord webhook | Implemented | `DISCORD_WEBHOOK_URL` (Railway variable). Mentions are disabled; the URL is never logged. |
| Email | Not implemented | No provider is configured, so there is no email code path. See below. |
| Browser push | Not implemented | Needs a push service and subscription storage, which static GitHub Pages hosting cannot provide. The RSS feed (`/feed.xml`) and PWA install cover "outside the browser tab" for now. |

## Adding a channel

A channel is any object with this shape (`delivery.DeliveryChannel`):

```python
class ExampleChannel:
    name = "example"

    def configured(self) -> bool:
        # True only when every credential the channel needs is present.
        ...

    def send(self, publication: Publication) -> bool:
        # Render publication.title / summary / fields / url and send.
        # Return False on failure; never raise into the publishing job,
        # never log credentials.
        ...
```

Then add it to `configured_channels()`.

For email, a transactional provider (for example Postmark, Resend or Amazon SES) would need:

- a sender domain with SPF/DKIM set up,
- an API key stored as a Railway variable (never committed),
- a subscriber list with double opt-in and one-click unsubscribe, which needs storage outside this static site.

Until those exist, email stays a documented extension point.
