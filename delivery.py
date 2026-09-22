"""Publication delivery for The Daily Tape.

A delivery channel receives a normalized `Publication` and decides how to
render it. Discord (webhook) is the only channel implemented. Email and push
are documented extension points (see docs/DELIVERY.md); no fake email
sending exists here.

Channels are only used after a new artifact has actually been committed, so
a run that finds no new session never posts.
"""

import dataclasses
import datetime
import json
import os
import sys
import urllib.request
from typing import Protocol

BRAND_ORANGE = 0xFF5C35
SUCCESS_GREEN = 0x2ECC71
FAILURE_RED = 0xE74C3C


@dataclasses.dataclass(frozen=True)
class Publication:
    kind: str  # "close" | "morning" | "failure"
    title: str
    url: str
    summary: str
    fields: tuple = ()  # ((name, value), ...)
    color: int = BRAND_ORANGE


class DeliveryChannel(Protocol):
    name: str

    def configured(self) -> bool: ...

    def send(self, publication: Publication) -> bool: ...


class DiscordWebhookChannel:
    name = "discord"

    def __init__(self, webhook_url=None, username="The Daily Tape", user_agent="market-summary-delivery"):
        self.webhook_url = webhook_url if webhook_url is not None else os.environ.get("DISCORD_WEBHOOK_URL", "")
        self.username = username
        self.user_agent = user_agent

    def configured(self):
        return bool(self.webhook_url)

    def payload(self, publication):
        return {
            "username": self.username,
            "allowed_mentions": {"parse": []},
            "embeds": [{
                "title": publication.title[:256],
                "url": publication.url,
                "description": publication.summary[:3500],
                "color": publication.color,
                "fields": [
                    {"name": str(name)[:256], "value": str(value)[:1024] or "—", "inline": True}
                    for name, value in publication.fields
                ][:25],
                "footer": {"text": "The Daily Tape"},
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }],
        }

    def send(self, publication):
        if not self.configured():
            print("DISCORD_WEBHOOK_URL is not set; skipping Discord delivery.")
            return False
        request = urllib.request.Request(
            self.webhook_url,
            data=json.dumps(self.payload(publication)).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": self.user_agent},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                response.read()
            print("Discord delivery sent.")
            return True
        except Exception as exc:
            # Never print the webhook URL; it is a credential.
            print(f"Warning: Discord delivery failed ({exc.__class__.__name__}).", file=sys.stderr)
            return False


def configured_channels():
    """Channels with credentials present. Email/push adapters would be added here."""
    return [channel for channel in (DiscordWebhookChannel(),) if channel.configured()]


def deliver(publication, channels=None):
    channels = configured_channels() if channels is None else channels
    return {channel.name: channel.send(publication) for channel in channels}


def _signed_pct(value):
    return f"{value:+.2f}%" if isinstance(value, (int, float)) and not isinstance(value, bool) else "Unavailable"


def _long_date(value):
    try:
        return datetime.date.fromisoformat(str(value)).strftime("%A, %B %-d, %Y")
    except (TypeError, ValueError):
        return str(value)


REGIME_NAMES = {"risk_on_confirmed": "Constructive", "risk_off_confirmed": "Defensive", "mixed": "Mixed"}
STATUS_NAMES = {"verified": "Verified", "partial": "Partial", "limited": "Limited"}


def close_publication(snapshot, site_url):
    """Discord-ready summary of a newly published Close Tape."""
    base = site_url.rstrip("/")
    session = snapshot.get("session_date")
    archive_url = f"{base}/reports/{session}/"
    market = snapshot.get("market_data", {})
    sp = market.get("^GSPC", {})
    breadth = snapshot.get("daily_market_breadth", {})
    sectors = len(snapshot.get("daily_sector_performance", {}))
    headline = (snapshot.get("narrative", {}).get("editorial") or {}).get("headline") or "The session closed."
    regime = REGIME_NAMES.get(((snapshot.get("derived_metrics") or {}).get("risk_confirmation") or {}).get("signal"), "Unavailable")
    quality = snapshot.get("data_quality") or {}
    fields = (
        ("Session", _long_date(session)),
        ("S&P 500", f"{_signed_pct(sp.get('pct_change'))} to {sp['end_price']:,.2f}" if isinstance(sp.get("end_price"), (int, float)) else "Unavailable"),
        ("Breadth", f"{breadth.get('advances', 0)} of {sectors} sectors up" if sectors else "Unavailable"),
        ("Regime", regime),
        ("Data status", STATUS_NAMES.get(quality.get("overall"), "Not recorded")),
        ("Archive", f"[Permanent link]({archive_url})"),
    )
    return Publication(
        kind="close",
        title=f"📈 {headline}",
        url=f"{base}/",
        summary=f"**The Daily Tape** for **{_long_date(session)}** is live.\n\n**[Read the Close Tape →]({base}/)**",
        fields=fields,
        color=SUCCESS_GREEN,
    )


def morning_publication(snapshot, site_url):
    morning_url = f"{site_url.rstrip('/')}/morning/"
    futures = snapshot.get("futures", {})
    es = futures.get("ES=F", {})
    items = snapshot.get("what_matters_today") or []
    first = items[0]["text"] if items and isinstance(items[0], dict) else (items[0] if items else None)
    fields = (
        ("Edition", _long_date(snapshot.get("market_date"))),
        ("S&P futures", _signed_pct(es.get("pct_change")) if not es.get("delayed") else "Delayed"),
        ("Quote coverage", f"{snapshot.get('data_quality', {}).get('coverage_pct', 0):.0f}%"),
        ("Status", str(snapshot.get("status", "")).title()),
    )
    return Publication(
        kind="morning",
        title="☀️ Morning Tape ready",
        url=morning_url,
        summary=(f"{first}\n\n" if first else "") + f"**[Open the Morning Tape →]({morning_url})**",
        fields=fields,
        color=BRAND_ORANGE,
    )


SECRET_ENVIRONMENT = ("GITHUB_TOKEN", "ANTHROPIC_API_KEY", "DISCORD_WEBHOOK_URL")


def redact(text):
    """Strip configured secret values from text before it leaves the process."""
    for name in SECRET_ENVIRONMENT:
        value = os.environ.get(name, "")
        if len(value) >= 8:
            text = text.replace(value, f"[{name} redacted]")
    return text


def failure_publication(error, site_url, service="Close Tape"):
    text = redact(str(error).strip() or error.__class__.__name__)
    if len(text) > 800:
        text = f"{text[:797]}..."
    return Publication(
        kind="failure",
        title=f"❌ {service} failed",
        url=site_url,
        summary=f"The Railway job failed before it could finish publishing.\n\n```text\n{text}\n```\n**[Open the last live report →]({site_url})**",
        fields=(("Status", "Failed"), ("Service", f"Railway · {service}")),
        color=FAILURE_RED,
    )
