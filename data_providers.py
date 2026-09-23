"""Normalized calendar and catalyst providers for The Daily Tape.

Every provider returns a FeedResult dict:

    {
        "id": "nasdaq_economic",          # stable feed id
        "name": "Nasdaq Economic Calendar",
        "source_url": "https://...",
        "status": "ok" | "empty" | "unavailable" | "disabled",
        "as_of": ISO-8601 UTC timestamp of the fetch, or None,
        "items": [...],                   # normalized items, never placeholders
        "error": short, secret-free reason or None,
    }

A failing provider never raises into the report pipeline. Missing data stays
missing: items are omitted rather than filled with guesses, and the feed status
records why. Feeds can be switched off with DAILY_TAPE_DISABLED_FEEDS, a
comma-separated list of feed ids.
"""

import datetime
import email.utils
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import trading_calendar

NY_TZ = ZoneInfo("America/New_York")
CENTRAL_TZ = ZoneInfo("America/Chicago")
USER_AGENT = "TheDailyTape/1.0 (contact: https://github.com/coolxng/market-summary/issues)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)
MAX_RESPONSE_BYTES = 3_000_000

FAIR_ECONOMY_CALENDAR_URLS = (
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
)
FOREX_FACTORY_CALENDAR_PAGE = "https://www.forexfactory.com/calendar"
TREASURY_AUCTIONS_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/upcoming_auctions"
TREASURY_AUCTIONS_PAGE = "https://fiscaldata.treasury.gov/datasets/upcoming-auctions/"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

OFFICIAL_FEEDS = (
    {
        "id": "fed_monetary",
        "name": "Federal Reserve press releases (monetary policy)",
        "publisher": "Federal Reserve",
        "url": "https://www.federalreserve.gov/feeds/press_monetary.xml",
        "category": "Monetary policy",
    },
    {
        "id": "fed_speeches",
        "name": "Federal Reserve speeches",
        "publisher": "Federal Reserve",
        "url": "https://www.federalreserve.gov/feeds/speeches.xml",
        "category": "Fed speech",
    },
    {
        "id": "bls_releases",
        "name": "U.S. Bureau of Labor Statistics releases",
        "publisher": "U.S. Bureau of Labor Statistics",
        "url": "https://www.bls.gov/feed/bls_latest.rss",
        "fallback_urls": (
            "https://www.bls.gov/feed/empsit.rss",
            "https://www.bls.gov/feed/cpi.rss",
            "https://www.bls.gov/feed/ppi.rss",
            "https://www.bls.gov/feed/jolts.rss",
        ),
        "category": "Economic data",
    },
    {
        "id": "bea_releases",
        "name": "U.S. Bureau of Economic Analysis releases",
        "publisher": "U.S. Bureau of Economic Analysis",
        "url": "https://apps.bea.gov/rss/rss.xml",
        "category": "Economic data",
    },
)

# Exact, normalized publisher names. Substring matching let unrelated outlets
# through (for example any name containing "sec"), so it is not used.
REPUTABLE_PUBLISHERS = {
    "reuters",
    "bloomberg",
    "bloomberg news",
    "cnbc",
    "associated press",
    "the associated press",
    "ap",
    "ap finance",
    "the wall street journal",
    "wall street journal",
    "dow jones newswires",
    "financial times",
    "marketwatch",
    "barrons",
    "yahoo finance",
}

ECONOMIC_CATEGORIES = (
    ("Central bank", r"\b(fomc|fed(eral reserve)?|interest rate decision|beige book|powell)\b"),
    ("Inflation", r"\b(cpi|ppi|pce|price index|inflation)\b"),
    ("Employment", r"\b(nonfarm|payrolls?|unemployment|jobless|jolts|adp|employment|labor)\b"),
    ("Growth", r"\b(gdp|gross domestic)\b"),
    ("Consumer", r"\b(retail sales|consumer (confidence|sentiment|credit)|michigan|personal (income|spending))\b"),
    ("Business surveys", r"\b(ism|pmi|empire state|philadelphia fed|philly fed|chicago pmi|durable goods|factory orders|industrial production)\b"),
    ("Housing", r"\b(housing|home sales|building permits|case-shiller|mortgage)\b"),
    ("Treasury auction", r"\bauction\b"),
    ("Energy", r"\b(eia|crude|natural gas|baker hughes)\b"),
    ("Trade", r"\b(trade balance|import|export)\b"),
)


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────
def _now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def disabled_feeds():
    raw = os.environ.get("DAILY_TAPE_DISABLED_FEEDS", "")
    return {value.strip() for value in raw.split(",") if value.strip()}


def feed_result(feed_id, name, source_url, items=None, error=None, status=None, as_of=None):
    items = list(items or [])
    if status is None:
        status = "unavailable" if error and not items else "ok" if items else "empty"
    return {
        "id": feed_id,
        "name": name,
        "source_url": source_url,
        "status": status,
        "as_of": as_of if as_of is not None else (_now_utc().isoformat() if status != "disabled" else None),
        "items": items,
        "error": error,
    }


def feed_meta(feed):
    """Feed status without its items, for the data-health panel."""
    return {key: value for key, value in feed.items() if key != "items"}


def http_get(url, accept="application/json", timeout=15, extra_headers=None, attempts=2):
    """Small, bounded GET helper with one retry for transient provider failures."""
    headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    headers.update(extra_headers or {})
    request = urllib.request.Request(url, headers=headers)
    last_error = None
    for attempt in range(max(1, attempts)):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            # Authentication/permission/schema errors are not transient. Retry only
            # rate limits and upstream/server failures.
            if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt + 1 >= attempts:
                raise
        except (TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                raise
    raise last_error


def clean_value(value):
    """Normalize provider cell values; blanks and dashes become None, never zero."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = html.unescape(str(value)).replace("\xa0", " ").strip()
    if text in {"", "-", "--", "—", "N/A", "n/a", "NA"}:
        return None
    return text


def classify_economic_event(title):
    lowered = title.lower()
    for category, pattern in ECONOMIC_CATEGORIES:
        if re.search(pattern, lowered):
            return category
    return "Economic data"


def _central_label(moment):
    return moment.astimezone(CENTRAL_TZ).strftime("%-I:%M %p CT")


def _run(feed_id, name, source_url, fetcher):
    if feed_id in disabled_feeds():
        return feed_result(feed_id, name, source_url, status="disabled", error="Disabled by DAILY_TAPE_DISABLED_FEEDS.")
    try:
        return feed_result(feed_id, name, source_url, items=fetcher())
    except Exception as exc:  # network, schema and parsing failures are all non-fatal
        print(f"  {name} unavailable: {exc.__class__.__name__}")
        return feed_result(feed_id, name, source_url, error=f"{name} unavailable ({exc.__class__.__name__}).")


# ─────────────────────────────────────────────
# Calendar providers
# ─────────────────────────────────────────────
def _parse_fair_economy_datetime(raw):
    text = str(raw or "").strip()
    if not text:
        return None
    # The feed normally uses ISO-8601 offsets such as -04:00. Accept the
    # compact -0400 form too so a harmless formatting change does not break it.
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=NY_TZ)
    return moment


def parse_fair_economy_rows(rows, days, countries=("USD",)):
    """Normalize Fair Economy rows using each row's explicit timestamp.

    The old Nasdaq feed exposed only a clock field whose date/timezone proved
    unreliable in production. This feed supplies a full ISO-8601 timestamp
    with an explicit UTC offset, so the Central date and time come from that
    timestamp instead of being inferred from the requested date.
    """
    wanted = {day.isoformat() for day in days}
    allowed = {country.upper() for country in countries}
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        country = str(row.get("country") or "").strip().upper()
        if allowed and country not in allowed:
            continue
        impact = clean_value(row.get("impact"))
        if str(impact or "").lower() == "holiday":
            continue
        title = clean_value(row.get("title") or row.get("event") or row.get("name"))
        moment = _parse_fair_economy_datetime(row.get("date"))
        if not title or moment is None:
            continue
        local = moment.astimezone(CENTRAL_TZ)
        local_date = local.date().isoformat()
        if local_date not in wanted:
            continue
        source_local = moment.astimezone(NY_TZ)
        items.append({
            "date": local_date,
            "time": _central_label(moment),
            "time_status": "scheduled",
            "starts_at": local.isoformat(),
            "source_time": source_local.strftime("%-I:%M %p"),
            "source_time_zone": "ET",
            "sort_key": local.strftime("%H:%M"),
            "title": title,
            "category": classify_economic_event(title),
            "kind": "economic",
            "country": "United States",
            "importance": impact,
            "actual": clean_value(row.get("actual")),
            "consensus": clean_value(row.get("forecast") or row.get("consensus")),
            "previous": clean_value(row.get("previous")),
            "source": "Forex Factory Economic Calendar",
            "source_url": FOREX_FACTORY_CALENDAR_PAGE,
        })
    return items


def fair_economy_economic_calendar(days):
    def fetch():
        items = {}
        successes = 0
        last_error = None
        for url in FAIR_ECONOMY_CALENDAR_URLS:
            try:
                payload = json.loads(http_get(
                    url,
                    accept="application/json, text/plain, */*",
                    timeout=12,
                    attempts=2,
                    extra_headers={
                        "User-Agent": BROWSER_USER_AGENT,
                        "Referer": FOREX_FACTORY_CALENDAR_PAGE,
                    },
                ))
                if not isinstance(payload, list):
                    raise ValueError("unexpected response shape")
            except Exception as exc:
                last_error = exc
                continue
            successes += 1
            for item in parse_fair_economy_rows(payload, days):
                items[(item["starts_at"], item["title"])] = item
        if not successes:
            raise last_error or ConnectionError("no economic-calendar week could be fetched")
        return list(items.values())

    return _run(
        "fair_economy_economic",
        "Forex Factory Economic Calendar",
        FOREX_FACTORY_CALENDAR_PAGE,
        fetch,
    )


def _format_offering(amount):
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return f"${value / 1e9:,.0f}B" if value >= 1e9 else f"${value / 1e6:,.0f}M"


def parse_treasury_auctions(records, days):
    wanted = {day.isoformat() for day in days}
    items = []
    for record in records:
        if not isinstance(record, dict):
            continue
        auction_date = str(record.get("auction_date") or "")[:10]
        if auction_date not in wanted:
            continue
        term = clean_value(record.get("security_term"))
        security = clean_value(record.get("security_type"))
        if not term or not security:
            continue
        reopening = str(record.get("reopening") or "").strip().lower() in {"yes", "y", "true"}
        items.append({
            "date": auction_date,
            "time": None,
            "time_status": "tbd",
            "sort_key": "99:97",
            "title": f"{term} {security} auction{' (reopening)' if reopening else ''}",
            "category": "Treasury auction",
            "kind": "auction",
            "country": "United States",
            "importance": None,
            "detail": " · ".join(filter(None, [
                f"Offering {_format_offering(record.get('offering_amt'))}" if _format_offering(record.get("offering_amt")) else None,
                f"CUSIP {record['cusip']}" if clean_value(record.get("cusip")) else None,
            ])) or None,
            "source": "U.S. Treasury Fiscal Data",
            "source_url": TREASURY_AUCTIONS_PAGE,
        })
    return items


def treasury_auction_calendar(days):
    def fetch():
        query = urllib.parse.urlencode({"sort": "auction_date", "page[size]": "100"})
        payload = json.loads(http_get(f"{TREASURY_AUCTIONS_URL}?{query}"))
        records = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise ValueError("unexpected response shape")
        return parse_treasury_auctions(records, days)

    return _run("treasury_auctions", "U.S. Treasury upcoming auctions", TREASURY_AUCTIONS_PAGE, fetch)


def _as_date(raw):
    if raw is None:
        return None
    if hasattr(raw, "to_pydatetime"):
        raw = raw.to_pydatetime()
    if isinstance(raw, datetime.datetime):
        return raw.date()
    if isinstance(raw, datetime.date):
        return raw
    try:
        return datetime.date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def parse_yahoo_earnings(ticker, calendar, days):
    if not isinstance(calendar, dict):
        return []
    raw_dates = calendar.get("Earnings Date") or calendar.get("Earnings Dates") or []
    if not isinstance(raw_dates, (list, tuple)):
        raw_dates = [raw_dates]
    dates = sorted({day for day in (_as_date(raw) for raw in raw_dates) if day})
    if not dates:
        return []
    wanted = {day.isoformat() for day in days}
    estimated_window = len(dates) > 1
    if dates[0].isoformat() not in wanted:
        return []
    eps = calendar.get("Earnings Average")
    eps = eps if isinstance(eps, (int, float)) and not isinstance(eps, bool) else None
    return [{
        "date": dates[0].isoformat(),
        "time": None,
        "time_status": "tbd",
        "sort_key": "99:96",
        "ticker": ticker,
        "title": f"{ticker} earnings",
        "category": "Earnings",
        "kind": "earnings",
        "importance": None,
        "date_status": "estimated_window" if estimated_window else "listed",
        "detail": (
            f"Estimated window {dates[0].strftime('%b %-d')}–{dates[-1].strftime('%b %-d')}" if estimated_window else "Release time not provided"
        ),
        "consensus": f"EPS est. {eps:.2f}" if eps is not None else None,
        "source": "Yahoo Finance company calendar",
        "source_url": f"https://finance.yahoo.com/quote/{ticker}/",
    }]


def yahoo_earnings_calendar(tickers, days, ticker_factory=None):
    def fetch():
        factory = ticker_factory
        if factory is None:
            import yfinance as yf
            factory = getattr(yf, "Ticker", None)
        if not callable(factory):
            raise RuntimeError("yfinance unavailable")
        items = []
        failures = 0
        tickers_list = list(dict.fromkeys(tickers))
        for ticker in tickers_list:
            try:
                items.extend(parse_yahoo_earnings(ticker, factory(ticker).calendar, days))
            except Exception:
                failures += 1
        if tickers_list and failures == len(tickers_list):
            raise ConnectionError("no company calendar could be fetched")
        return items

    return _run("yahoo_earnings", "Yahoo Finance company calendar (tracked names)", "https://finance.yahoo.com/calendar/earnings", fetch)


def market_structure_calendar(days):
    return _run(
        "market_structure",
        "NYSE and expiration rules",
        trading_calendar.NYSE_HOURS_URL,
        lambda: trading_calendar.market_structure_events(days),
    )


def _session_label(date_text, days):
    if days and date_text == days[0].isoformat():
        return "current"
    if len(days) > 1 and date_text == days[-1].isoformat():
        return "next"
    return "between"


def build_market_calendar(anchor, earnings_tickers, providers=None):
    """Current trading session (when `anchor` trades) plus the next session."""
    days = trading_calendar.session_window(anchor)
    if providers is None:
        providers = (
            lambda d: fair_economy_economic_calendar(d),
            lambda d: treasury_auction_calendar(d),
            lambda d: yahoo_earnings_calendar(earnings_tickers, d),
            lambda d: market_structure_calendar(d),
        )
    feeds = [provider(days) for provider in providers]
    items = []
    for feed in feeds:
        for item in feed["items"]:
            items.append({**item, "session": _session_label(item["date"], days)})
    items.sort(key=lambda item: (item["date"], item.get("sort_key") or "99:99", item["title"]))
    for item in items:
        item.pop("sort_key", None)
    return {
        "window": {
            "current_session": days[0].isoformat() if trading_calendar.is_trading_day(anchor) else None,
            "next_session": days[-1].isoformat(),
            "display_time_zone": "America/Chicago",
        },
        "items": items,
        "feeds": [feed_meta(feed) for feed in feeds],
        "note": "Scheduled events are listed with their source. Importance is shown only when the provider supplies it; none is inferred.",
    }


# ─────────────────────────────────────────────
# Catalyst providers
# ─────────────────────────────────────────────
def _parse_timestamp(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return int(parsed.timestamp())


def parse_feed_xml(text):
    """Parse RSS 2.0 or Atom into (title, link, timestamp) tuples."""
    root = ET.fromstring(text)
    entries = []
    for item in root.iter():
        tag = item.tag.rsplit("}", 1)[-1]
        if tag not in {"item", "entry"}:
            continue
        fields = {}
        for child in item:
            name = child.tag.rsplit("}", 1)[-1]
            if name == "link" and child.get("href"):
                fields.setdefault("link", child.get("href"))
            elif child.text:
                fields.setdefault(name, child.text.strip())
        title = clean_value(fields.get("title"))
        link = clean_value(fields.get("link"))
        timestamp = _parse_timestamp(fields.get("pubDate") or fields.get("date") or fields.get("updated") or fields.get("published"))
        if title and link and link.startswith("https://"):
            entries.append((re.sub(r"\s+", " ", title), link, timestamp))
    return entries


def official_catalysts(feed, start, end):
    def fetch():
        items = {}
        successes = 0
        last_error = None
        urls = (feed["url"], *feed.get("fallback_urls", ()))
        for url in urls:
            try:
                is_bls = "bls.gov" in url
                raw = http_get(
                    url,
                    accept="application/rss+xml, application/xml, text/xml, */*",
                    timeout=12,
                    # BLS explicitly rate-limits/blocklists automated retrieval.
                    # Do not multiply requests from a blocked Railway IP.
                    attempts=1 if is_bls else 2,
                    extra_headers={"Referer": "https://www.bls.gov/feed/"} if is_bls else None,
                )
                entries = parse_feed_xml(raw)
                successes += 1
            except urllib.error.HTTPError as exc:
                last_error = exc
                # A BLS 403 is an explicit provider block, not a transient outage.
                # Trying four more paths from the same IP is counterproductive and
                # can worsen the block, so fail closed after the first response.
                if feed["id"] == "bls_releases" and exc.code == 403:
                    raise PermissionError("BLS blocked automated retrieval") from exc
                continue
            except Exception as exc:
                last_error = exc
                continue
            for title, link, timestamp in entries:
                if timestamp is None or not (start.timestamp() <= timestamp <= end.timestamp()):
                    continue
                items[link] = {
                    "title": title,
                    "url": link,
                    "publisher": feed["publisher"],
                    "published_at": timestamp,
                    "category": feed["category"],
                    "source_type": "official",
                    "related_tickers": [],
                }
            # The aggregate feed is authoritative when it succeeds. Specific BLS
            # feeds are only fallbacks for hosts that block bls_latest.rss.
            if url == feed["url"]:
                break
        if not successes:
            raise last_error or ConnectionError("no official feed endpoint succeeded")
        return list(items.values())

    return _run(feed["id"], feed["name"], feed["url"], fetch)


def normalize_publisher(name):
    return re.sub(r"[^a-z ]", "", str(name or "").lower().replace(".com", "")).strip()


def normalize_news_item(raw):
    if not isinstance(raw, dict):
        return None
    title = clean_value(raw.get("title"))
    link = clean_value(raw.get("link") or raw.get("url"))
    publisher = clean_value(raw.get("publisher") or raw.get("provider"))
    timestamp = raw.get("providerPublishTime") or raw.get("published_at")
    if isinstance(timestamp, datetime.datetime):
        timestamp = int(timestamp.timestamp())
    try:
        timestamp = int(timestamp) if timestamp is not None else None
    except (TypeError, ValueError):
        timestamp = None
    if not title or not link or not publisher or timestamp is None or not str(link).startswith("https://"):
        return None
    if normalize_publisher(publisher) not in REPUTABLE_PUBLISHERS:
        return None
    return {
        "title": title,
        "url": link,
        "publisher": publisher,
        "published_at": timestamp,
        "category": "Market news",
        "source_type": "news",
        "related_tickers": [str(value) for value in raw.get("relatedTickers", []) if value][:6],
    }


def _yahoo_search_news(query, count):
    params = urllib.parse.urlencode({"q": query, "quotesCount": 0, "newsCount": count, "listsCount": 0})
    payload = json.loads(http_get(f"{YAHOO_SEARCH_URL}?{params}"))
    return payload.get("news", []) if isinstance(payload, dict) else []


def reputable_news_catalysts(start, end, queries=("stock market", "Federal Reserve", "Treasury yields", "technology stocks")):
    def fetch():
        collected = {}
        failures = 0
        for query in queries:
            try:
                raw_items = _yahoo_search_news(query, 10)
            except Exception:
                failures += 1
                continue
            for raw in raw_items:
                item = normalize_news_item(raw)
                if item and start.timestamp() <= item["published_at"] <= end.timestamp():
                    collected[item["url"]] = item
        if failures == len(queries):
            raise ConnectionError("no news query succeeded")
        return list(collected.values())

    return _run("yahoo_news", "Yahoo Finance news search (allowlisted publishers)", "https://finance.yahoo.com/topic/stock-market-news/", fetch)


def build_verified_catalysts(start, end, max_items=6, providers=None):
    """Source-linked developments published inside [start, end].

    Official releases are listed first; reputable news fills remaining slots.
    Items carry their own publisher, link and timestamp and are never used as
    causal explanations for market moves.
    """
    if providers is None:
        providers = [lambda s, e, f=feed: official_catalysts(f, s, e) for feed in OFFICIAL_FEEDS]
        providers.append(lambda s, e: reputable_news_catalysts(s, e))
    feeds = [provider(start, end) for provider in providers]
    official, news = [], []
    seen = set()
    for feed in feeds:
        for item in feed["items"]:
            key = item["url"]
            if key in seen:
                continue
            seen.add(key)
            (official if item.get("source_type") == "official" else news).append(item)
    official.sort(key=lambda item: item["published_at"], reverse=True)
    news.sort(key=lambda item: item["published_at"], reverse=True)
    selected = (official[: max_items - min(len(news), max_items // 2)] + news)[:max_items]
    selected.sort(key=lambda item: item["published_at"], reverse=True)
    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "items": selected,
        "feeds": [feed_meta(feed) for feed in feeds],
        "label": "Source-linked developments published during this window. Listed as context; not claimed causes of market moves.",
    }


def summarize_feed_health(feed_groups):
    """Collapse feed statuses into one of: verified, partial, unavailable."""
    statuses = [feed["status"] for group in feed_groups for feed in group if feed["status"] != "disabled"]
    if not statuses:
        return "unavailable"
    if all(status in {"ok", "empty"} for status in statuses):
        return "verified"
    if any(status in {"ok", "empty"} for status in statuses):
        return "partial"
    return "unavailable"
