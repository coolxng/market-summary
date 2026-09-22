import datetime
import json
import math
import os
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import yfinance as yf


NY_TZ = ZoneInfo("America/New_York")
CENTRAL_TZ = ZoneInfo("America/Chicago")
USER_AGENT = "Mozilla/5.0 (compatible; TheDailyTape/1.0; +https://coolxng.github.io/market-summary/)"
NASDAQ_CALENDAR_URL = "https://api.nasdaq.com/api/calendar/economicevents"
NASDAQ_CALENDAR_PAGE = "https://www.nasdaq.com/market-activity/economic-calendar"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

REPUTABLE_NEWS_PUBLISHERS = (
    "reuters",
    "bloomberg",
    "cnbc",
    "associated press",
    "ap finance",
    "wall street journal",
    "wsj",
    "financial times",
    "marketwatch",
    "barron",
    "yahoo finance",
    "federal reserve",
    "securities and exchange commission",
    "sec",
)


def _runtime_data_available():
    # Unit tests install a deliberately minimal yfinance stub with Ticker=None.
    return callable(getattr(yf, "Ticker", None))


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _index_date(value):
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value)[:10])


def _safe_float(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _pct_change(current, previous):
    if not _finite(current) or not _finite(previous) or previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 2)


def _period_return(closes, sessions):
    if len(closes) <= sessions:
        return None
    return _pct_change(closes[-1], closes[-(sessions + 1)])


def fetch_history_snapshot(symbol, session_date, lookback_days=400):
    """Fetch compact daily history and common finance-user reference metrics."""
    if not _runtime_data_available():
        return {
            "symbol": symbol,
            "dates": [],
            "closes": [],
            "returns": {"5d": None, "1m": None, "3m": None, "ytd": None, "1y": None},
            "moving_averages": {"20d": None, "50d": None, "200d": None},
            "above_moving_average": {"20d": None, "50d": None, "200d": None},
            "source": "Yahoo Finance via yfinance",
            "as_of": None,
            "error": "history unavailable",
        }
    try:
        hist = yf.Ticker(symbol).history(
            start=(session_date - datetime.timedelta(days=lookback_days)).isoformat(),
            end=(session_date + datetime.timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=False,
        )
        hist = hist.dropna(subset=["Close"])
        rows = [
            (position, _index_date(value))
            for position, value in enumerate(hist.index)
            if _index_date(value) <= session_date
        ]
        if len(rows) < 2:
            raise ValueError("fewer than two daily bars")

        dates = [day.isoformat() for _, day in rows[-260:]]
        closes = [round(float(hist["Close"].iloc[position]), 4) for position, _ in rows[-260:]]
        current = closes[-1]

        year_start_index = next(
            (index for index, date in enumerate(dates) if date.startswith(f"{session_date.year}-")),
            None,
        )
        ytd = None
        if year_start_index is not None and year_start_index < len(closes) - 1:
            ytd = _pct_change(current, closes[year_start_index])

        def sma(window):
            if len(closes) < window:
                return None
            return round(sum(closes[-window:]) / window, 4)

        sma20 = sma(20)
        sma50 = sma(50)
        sma200 = sma(200)
        return {
            "symbol": symbol,
            "dates": dates,
            "closes": closes,
            "returns": {
                "5d": _period_return(closes, 5),
                "1m": _period_return(closes, 21),
                "3m": _period_return(closes, 63),
                "ytd": ytd,
                "1y": _period_return(closes, min(252, len(closes) - 1)),
            },
            "moving_averages": {
                "20d": sma20,
                "50d": sma50,
                "200d": sma200,
            },
            "above_moving_average": {
                "20d": None if sma20 is None else current > sma20,
                "50d": None if sma50 is None else current > sma50,
                "200d": None if sma200 is None else current > sma200,
            },
            "source": "Yahoo Finance via yfinance",
            "as_of": dates[-1],
            "error": None,
        }
    except Exception as exc:
        print(f"  History unavailable for {symbol}: {exc}")
        return {
            "symbol": symbol,
            "dates": [],
            "closes": [],
            "returns": {"5d": None, "1m": None, "3m": None, "ytd": None, "1y": None},
            "moving_averages": {"20d": None, "50d": None, "200d": None},
            "above_moving_average": {"20d": None, "50d": None, "200d": None},
            "source": "Yahoo Finance via yfinance",
            "as_of": None,
            "error": "history unavailable",
        }


def fetch_history_bundle(symbols, session_date):
    return {symbol: fetch_history_snapshot(symbol, session_date) for symbol in dict.fromkeys(symbols)}


def _normalize_news_item(item):
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()
    link = str(item.get("link") or item.get("url") or "").strip()
    publisher = str(item.get("publisher") or item.get("provider") or "").strip()
    published = item.get("providerPublishTime") or item.get("published_at")
    if not title or not link:
        return None
    if isinstance(published, datetime.datetime):
        published = int(published.timestamp())
    try:
        published = int(published) if published is not None else None
    except (TypeError, ValueError):
        published = None
    related_tickers = [str(value) for value in item.get("relatedTickers", []) if value]
    return {
        "title": title,
        "url": link,
        "publisher": publisher or "Unknown publisher",
        "published_at": published,
        "related_tickers": related_tickers,
        "affected_assets": related_tickers,
        "category": "Market news",
    }


def _yahoo_news_via_search(query, count):
    search_class = getattr(yf, "Search", None)
    if search_class is None:
        return []
    result = search_class(
        query,
        max_results=0,
        news_count=count,
        lists_count=0,
        include_cb=False,
        include_nav_links=False,
        include_research=False,
        recommended=0,
        timeout=15,
        raise_errors=False,
    )
    return getattr(result, "news", []) or []


def _yahoo_news_via_http(query, count):
    params = urllib.parse.urlencode({
        "q": query,
        "quotesCount": 0,
        "newsCount": count,
        "listsCount": 0,
    })
    request = urllib.request.Request(
        f"{YAHOO_SEARCH_URL}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("news", []) if isinstance(payload, dict) else []


def fetch_market_headlines(session_date, queries=None, max_items=8):
    """Collect source-linked headlines. They are context, never causal attribution."""
    if not _runtime_data_available():
        return {
            "items": [],
            "source": "Yahoo Finance search/news",
            "as_of": None,
            "label": "Source-linked headlines; not claimed causes of market moves.",
            "error": "No verified headlines returned.",
        }
    queries = queries or ("stock market", "Federal Reserve", "Treasury yields", "technology stocks")
    collected = {}
    session_close = datetime.datetime.combine(session_date, datetime.time(16, 0), tzinfo=NY_TZ)
    earliest = session_close - datetime.timedelta(hours=36)
    latest = session_close + datetime.timedelta(hours=8)

    for query in queries:
        try:
            raw_items = _yahoo_news_via_search(query, max_items)
            if not raw_items:
                raw_items = _yahoo_news_via_http(query, max_items)
            for raw in raw_items:
                item = _normalize_news_item(raw)
                if not item:
                    continue
                publisher_key = item["publisher"].lower()
                if not any(name in publisher_key for name in REPUTABLE_NEWS_PUBLISHERS):
                    continue
                timestamp = item["published_at"]
                if timestamp is not None:
                    published_at = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).astimezone(NY_TZ)
                    if published_at < earliest or published_at > latest:
                        continue
                key = item["url"] or item["title"]
                collected[key] = item
        except Exception as exc:
            print(f"  News lookup unavailable for {query!r}: {exc}")

    items = sorted(
        collected.values(),
        key=lambda item: item["published_at"] or 0,
        reverse=True,
    )[:max_items]
    return {
        "items": items,
        "source": "Yahoo Finance search/news · reputable publishers only",
        "as_of": session_close.isoformat(),
        "label": "Source-linked developments from reputable publishers; not claimed causes of market moves.",
        "error": None if items else "No verified headlines returned.",
    }


def _nasdaq_rows_for_date(day):
    params = urllib.parse.urlencode({"date": day.isoformat()})
    request = urllib.request.Request(
        f"{NASDAQ_CALENDAR_URL}?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nasdaq.com/market-activity/economic-calendar",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return []
    rows = data.get("rows") or data.get("data") or []
    return rows if isinstance(rows, list) else []


def _calendar_time_fields(row, day):
    raw_gmt = str(row.get("gmt") or "").strip()
    if raw_gmt:
        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p"):
            try:
                clock = datetime.datetime.strptime(raw_gmt, fmt).time()
                utc_dt = datetime.datetime.combine(day, clock, tzinfo=datetime.timezone.utc)
                local_dt = utc_dt.astimezone(CENTRAL_TZ)
                return {
                    "time": local_dt.strftime("%-I:%M %p CT"),
                    "time_zone": "America/Chicago",
                    "source_time": raw_gmt,
                    "source_time_zone": "UTC",
                }
            except ValueError:
                continue

    raw_time = str(row.get("time") or row.get("releaseTime") or "").strip()
    source_zone = str(row.get("timezone") or row.get("timeZone") or "").strip() or None
    return {
        "time": raw_time or "TBD",
        "time_zone": source_zone,
        "source_time": raw_time or None,
        "source_time_zone": source_zone,
    }


def _calendar_event(row, day):
    if not isinstance(row, dict):
        return None
    title = (
        row.get("eventName")
        or row.get("event")
        or row.get("name")
        or row.get("indicator")
        or row.get("description")
    )
    if not title:
        return None
    country = str(row.get("country") or row.get("region") or "").strip()
    category = str(row.get("category") or row.get("eventType") or "Economic data").strip()
    importance = row.get("importance") or row.get("impact") or row.get("priority")
    time_fields = _calendar_time_fields(row, day)
    return {
        "date": day.isoformat(),
        **time_fields,
        "title": str(title).strip(),
        "category": category,
        "importance": importance,
        "country": country,
        "actual": row.get("actual"),
        "consensus": row.get("consensus") or row.get("forecast"),
        "previous": row.get("previous"),
        "source": "Nasdaq Economic Calendar",
        "source_url": NASDAQ_CALENDAR_PAGE,
    }


def fetch_economic_calendar(start_date, days=5, max_items=16):
    """Fetch a small upcoming economic calendar. Failure is non-fatal."""
    if not _runtime_data_available():
        return {
            "items": [],
            "source": "Nasdaq Economic Calendar",
            "as_of": None,
            "error": "Economic calendar unavailable.",
        }
    events = []
    for offset in range(days):
        day = start_date + datetime.timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        try:
            rows = _nasdaq_rows_for_date(day)
            events.extend(filter(None, (_calendar_event(row, day) for row in rows)))
        except Exception as exc:
            print(f"  Economic calendar unavailable for {day}: {exc}")
    return {
        "items": events[:max_items],
        "source": "Nasdaq Economic Calendar",
        "as_of": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "error": None if events else "Economic calendar unavailable.",
    }


def fetch_tracked_earnings(tickers, start_date, days=10, max_items=12):
    """Fetch upcoming earnings dates for the tracked leadership universe."""
    if not _runtime_data_available():
        return {
            "items": [],
            "source": "Yahoo Finance company calendar",
            "as_of": None,
            "error": "No tracked earnings returned in the window.",
        }
    end_date = start_date + datetime.timedelta(days=days)
    events = []
    for ticker in dict.fromkeys(tickers):
        try:
            calendar = yf.Ticker(ticker).calendar
            if not isinstance(calendar, dict):
                continue
            raw_dates = calendar.get("Earnings Date") or calendar.get("Earnings Dates") or []
            if not isinstance(raw_dates, (list, tuple)):
                raw_dates = [raw_dates]
            for raw in raw_dates:
                if raw is None:
                    continue
                if hasattr(raw, "to_pydatetime"):
                    raw = raw.to_pydatetime()
                if isinstance(raw, datetime.datetime):
                    day = raw.date()
                elif isinstance(raw, datetime.date):
                    day = raw
                else:
                    day = datetime.date.fromisoformat(str(raw)[:10])
                if start_date <= day <= end_date:
                    events.append({
                        "date": day.isoformat(),
                        "ticker": ticker,
                        "title": f"{ticker} earnings",
                        "time": "TBD",
                        "time_zone": None,
                        "category": "Earnings",
                        "importance": None,
                        "source": "Yahoo Finance company calendar",
                        "source_url": f"https://finance.yahoo.com/quote/{ticker}/",
                    })
        except Exception as exc:
            print(f"  Earnings calendar unavailable for {ticker}: {exc}")
    events.sort(key=lambda item: (item["date"], item["ticker"]))
    return {
        "items": events[:max_items],
        "source": "Yahoo Finance company calendar",
        "as_of": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "error": None if events else "No tracked earnings returned in the window.",
    }


def build_data_quality(datasets, expected_session):
    issues = []
    sources = {}
    valid = 0
    for symbol, row in datasets.items():
        source = row.get("data_source") or "yahoo_finance"
        sources[source] = sources.get(source, 0) + 1
        if row.get("error"):
            issues.append(f"{symbol}: unavailable")
            continue
        if row.get("session_date") != expected_session.isoformat():
            issues.append(f"{symbol}: stale session {row.get('session_date') or 'unknown'}")
            continue
        if not _finite(row.get("end_price")) or row.get("end_price", 0) <= 0:
            issues.append(f"{symbol}: invalid close")
            continue
        valid += 1

    total = len(datasets)
    coverage = round((valid / total) * 100, 1) if total else 0.0
    status = "healthy" if coverage == 100 and not issues else "degraded" if coverage >= 85 else "limited"
    return {
        "status": status,
        "valid": valid,
        "total": total,
        "coverage_pct": coverage,
        "issues": issues,
        "sources": sources,
        "checked_session": expected_session.isoformat(),
    }
