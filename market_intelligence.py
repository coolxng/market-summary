import datetime
import math
from zoneinfo import ZoneInfo

import yfinance as yf


NY_TZ = ZoneInfo("America/New_York")
CENTRAL_TZ = ZoneInfo("America/Chicago")
USER_AGENT = "Mozilla/5.0 (compatible; TheDailyTape/1.0; +https://coolxng.github.io/market-summary/)"


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


def build_data_quality(datasets, expected_session, feed_groups=(), local_calendar_symbols=(), previous_session=None):
    """Market-data coverage plus external feed health for the trust panel.

    `status` keeps the historical healthy/degraded/limited market-data scale.
    `overall` is what readers see: verified, partial, or limited.

    Instruments on other calendars (overseas indexes, 24/7 crypto) are checked
    against the prior U.S. session instead of the report session; when their
    latest local session differs it is recorded in `local_sessions` so the UI
    can label the date rather than implying a same-day close.
    """
    issues = []
    sources = {}
    local_sessions = {}
    valid = 0
    local_symbols = set(local_calendar_symbols)
    for symbol, row in datasets.items():
        source = row.get("data_source") or "yahoo_finance"
        sources[source] = sources.get(source, 0) + 1
        if row.get("error"):
            issues.append(f"{symbol}: unavailable")
            continue
        row_session = row.get("session_date")
        if symbol in local_symbols and row_session and row_session != expected_session.isoformat():
            floor = (previous_session or expected_session).isoformat()
            if row_session >= floor and row_session <= expected_session.isoformat():
                local_sessions[symbol] = row_session
                valid += 1
                continue
        if row_session != expected_session.isoformat():
            issues.append(f"{symbol}: stale session {row.get('session_date') or 'unknown'}")
            continue
        if not _finite(row.get("end_price")) or row.get("end_price", 0) <= 0:
            issues.append(f"{symbol}: invalid close")
            continue
        valid += 1

    total = len(datasets)
    coverage = round((valid / total) * 100, 1) if total else 0.0
    status = "healthy" if coverage == 100 and not issues else "degraded" if coverage >= 85 else "limited"
    feeds = [feed for group in feed_groups for feed in group]
    unavailable = [feed["name"] for feed in feeds if feed.get("status") == "unavailable"]
    if status == "limited":
        overall = "limited"
    elif status == "healthy" and not unavailable:
        overall = "verified"
    else:
        overall = "partial"
    return {
        "status": status,
        "overall": overall,
        "valid": valid,
        "total": total,
        "coverage_pct": coverage,
        "issues": issues,
        "sources": sources,
        "checked_session": expected_session.isoformat(),
        "local_sessions": local_sessions,
        "feeds": feeds,
        "unavailable_feeds": unavailable,
    }
