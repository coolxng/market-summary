import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

import trading_calendar
from data_providers import build_market_calendar, build_verified_catalysts
from official_rates import fetch_treasury_rates


NY_TZ = ZoneInfo("America/New_York")
TRACKED_EARNINGS = ("AAPL", "MSFT", "NVDA", "AMZN", "META", "AMD", "INTC", "MU", "SNDK")
# Quotes older than this at generation time are labeled delayed.
FRESHNESS_LIMIT_MINUTES = {"futures": 90, "cross_asset": 180, "global_markets": None}

FUTURES = {
    "ES=F": {"name": "S&P 500 E-mini futures"},
    "NQ=F": {"name": "Nasdaq 100 E-mini futures"},
    "YM=F": {"name": "Dow E-mini futures"},
    "RTY=F": {"name": "Russell 2000 E-mini futures"},
}

CROSS_ASSET = {
    "^VIX": {"name": "Cboe Volatility Index", "note": "Previous close until the cash session opens."},
    "2YY=F": {"name": "CBOT 2-Year yield futures", "proxy": True, "note": "Futures proxy for the 2-year yield, not the cash Treasury yield."},
    "^TNX": {"name": "10-Year Treasury yield index (Cboe)", "note": "Updates during U.S. hours only."},
    "DX-Y.NYB": {"name": "U.S. Dollar Index"},
    "GC=F": {"name": "Gold futures"},
    "CL=F": {"name": "WTI crude futures"},
    "BTC-USD": {"name": "Bitcoin"},
    "ETH-USD": {"name": "Ethereum"},
}

GLOBAL = {
    "^N225": {"name": "Nikkei 225", "region": "Asia"},
    "^HSI": {"name": "Hang Seng", "region": "Asia"},
    "^STOXX50E": {"name": "Euro Stoxx 50", "region": "Europe"},
    "^FTSE": {"name": "FTSE 100", "region": "Europe"},
}


def market_now(now=None):
    value = now or datetime.datetime.now(NY_TZ)
    if value.tzinfo is None:
        value = value.replace(tzinfo=NY_TZ)
    return value.astimezone(NY_TZ)


def _bar_date(value):
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=NY_TZ)
        return value.astimezone(NY_TZ).date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value)[:10])


def _as_datetime(value):
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=NY_TZ)
    return None


def latest_quote(symbol, now=None, freshness_limit_minutes=None):
    """Return the latest quote versus the latest completed daily reference close."""
    current = market_now(now)
    try:
        ticker = yf.Ticker(symbol)
        daily = ticker.history(period="5d", interval="1d", auto_adjust=False).dropna(subset=["Close"])
        intraday = ticker.history(period="2d", interval="5m", prepost=True, auto_adjust=False).dropna(subset=["Close"])
        if len(daily) < 1:
            raise ValueError("insufficient daily bars")

        reference_positions = [
            index for index, value in enumerate(daily.index)
            if _bar_date(value) < current.date()
        ]
        if not reference_positions:
            raise ValueError("no completed daily reference close")
        reference_position = reference_positions[-1]
        reference = float(daily["Close"].iloc[reference_position])
        reference_date = _bar_date(daily.index[reference_position]).isoformat()

        has_intraday = len(intraday) > 0
        if has_intraday:
            latest = float(intraday["Close"].iloc[-1])
            timestamp = intraday.index[-1]
        else:
            latest = float(daily["Close"].iloc[-1])
            timestamp = daily.index[-1]
        latest_date = _bar_date(timestamp)

        stale = not has_intraday and latest_date < current.date()
        moment = _as_datetime(timestamp)
        age_minutes = None
        if moment is not None:
            age_minutes = max(0, round((current - moment.astimezone(NY_TZ)).total_seconds() / 60))
            timestamp = moment.astimezone(NY_TZ).isoformat()
        else:
            timestamp = str(timestamp)
        delayed = bool(
            freshness_limit_minutes is not None
            and age_minutes is not None
            and age_minutes > freshness_limit_minutes
        )

        pct = None
        if not stale and reference:
            pct = round(((latest - reference) / reference) * 100, 2)

        return {
            "symbol": symbol,
            "price": round(latest, 4),
            "reference_close": round(reference, 4),
            "reference_date": reference_date,
            "pct_change": pct,
            "timestamp": timestamp,
            "age_minutes": age_minutes,
            "stale": stale,
            "delayed": delayed,
            "source": "Yahoo Finance via yfinance",
            "error": None,
        }
    except Exception as exc:
        print(f"  Morning quote unavailable for {symbol}: {exc}")
        return {
            "symbol": symbol,
            "price": None,
            "reference_close": None,
            "reference_date": None,
            "pct_change": None,
            "timestamp": None,
            "age_minutes": None,
            "stale": False,
            "delayed": False,
            "source": "Yahoo Finance via yfinance",
            "error": "quote unavailable",
        }


def _quotes(group, table, current):
    limit = FRESHNESS_LIMIT_MINUTES[group]
    return {symbol: {**meta, **latest_quote(symbol, current, limit)} for symbol, meta in table.items()}


def _short_date(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10]).strftime("%b %-d")
    except ValueError:
        return str(value)


def _usable(quote):
    return quote.get("pct_change") is not None and not quote.get("stale") and not quote.get("delayed") and not quote.get("error")


def what_matters_today(market_date, futures, global_markets, calendar, catalysts, rates):
    """Deterministic, observed-only bullets. No forecasts or causal claims."""
    items = []
    valid_futures = [quote for quote in futures.values() if _usable(quote)]
    if valid_futures:
        es = futures.get("ES=F")
        lead = es if es in valid_futures else max(valid_futures, key=lambda quote: abs(quote["pct_change"]))
        others = [quote for quote in valid_futures if quote is not lead]
        widest = max(others, key=lambda quote: abs(quote["pct_change"])) if others else None
        text = f'{lead["name"]} {lead["pct_change"]:+.2f}% versus the {_short_date(lead["reference_date"])} daily close.'
        if widest:
            text += f' Widest index move: {widest["name"]} {widest["pct_change"]:+.2f}%.'
        items.append({"label": "Futures", "text": text})

    asia = [quote for quote in global_markets.values() if quote.get("region") == "Asia" and _usable(quote)]
    europe = [quote for quote in global_markets.values() if quote.get("region") == "Europe" and _usable(quote)]
    if asia or europe:
        parts = [f'{quote["name"]} {quote["pct_change"]:+.2f}%' for quote in (*asia, *europe)]
        items.append({"label": "Overnight", "text": "; ".join(parts) + "."})

    today = market_date.isoformat()
    timed = [item for item in calendar["items"] if item["date"] == today and item.get("kind") == "economic" and item.get("time")]
    if timed:
        first = timed[0]
        more = f" and {len(timed) - 1} more scheduled U.S. release{'s' if len(timed) > 2 else ''}" if len(timed) > 1 else ""
        items.append({"label": "Calendar", "text": f'{first["title"]} at {first["time"]}{more}.'})
    earnings = [item for item in calendar["items"] if item["date"] == today and item.get("kind") == "earnings"]
    if earnings:
        names = ", ".join(item["ticker"] for item in earnings)
        items.append({"label": "Earnings", "text": f"Tracked names listed for today: {names} (times not published by the source)."})

    curve = (rates or {}).get("curve")
    spread = ((rates or {}).get("spreads") or {}).get("2s10s")
    if curve and "10y" in curve["tenors"]:
        ten = curve["tenors"]["10y"]["value"]
        text = f'Official 10-year Treasury {ten:.2f}% as of {_short_date(curve["as_of"])}'
        if spread:
            text += f'; 2s10s {spread["value_bp"]:+.0f} bps'
        items.append({"label": "Rates", "text": text + "."})

    if catalysts["items"]:
        first = catalysts["items"][0]
        items.append({"label": "News", "text": f'{first["title"]} ({first["publisher"]}).'})
    return items[:5]


def generate_morning_snapshot(now=None, snapshot_path="data/morning_snapshot.json", public_path="public/morning/latest.json"):
    current = market_now(now)
    market_date = current.date()

    print(f"Building Morning Tape for {market_date.isoformat()}...")
    futures = _quotes("futures", FUTURES, current)
    cross_asset = _quotes("cross_asset", CROSS_ASSET, current)
    global_markets = _quotes("global_markets", GLOBAL, current)

    market_calendar = build_market_calendar(market_date, TRACKED_EARNINGS)
    previous_session = trading_calendar.previous_trading_day(market_date)
    catalysts = build_verified_catalysts(
        datetime.datetime.combine(previous_session, datetime.time(16, 0), tzinfo=NY_TZ),
        current,
    )
    rates = fetch_treasury_rates(market_date)

    all_quotes = [*futures.values(), *cross_asset.values(), *global_markets.values()]
    valid = sum(
        1 for quote in all_quotes
        if not quote.get("error") and not quote.get("stale") and quote.get("price") is not None
    )
    coverage = round(valid / len(all_quotes) * 100, 1) if all_quotes else 0.0
    feeds = [*market_calendar["feeds"], *catalysts["feeds"], {k: v for k, v in rates.items() if k in {"id", "name", "source_url", "status", "as_of", "error"}}]

    snapshot = {
        "report_type": "morning_tape",
        "market_date": market_date.isoformat(),
        "trading_day": trading_calendar.is_trading_day(market_date),
        "previous_session": previous_session.isoformat(),
        "generated_at": current.isoformat(),
        "status": "ready" if coverage >= 80 else "partial",
        "data_quality": {
            "valid": valid,
            "total": len(all_quotes),
            "coverage_pct": coverage,
            "delayed": sorted(quote["symbol"] for quote in all_quotes if quote.get("delayed")),
            "feeds": feeds,
        },
        "futures": futures,
        "cross_asset": cross_asset,
        "global_markets": global_markets,
        "treasury_rates": rates,
        "market_calendar": market_calendar,
        "verified_catalysts": catalysts,
        "what_matters_today": what_matters_today(market_date, futures, global_markets, market_calendar, catalysts, rates),
        "notes": [
            "Futures and extended-hours moves are compared with the latest completed daily reference close.",
            "Official Treasury yields are the latest published end-of-day par curve, labeled with their own date.",
            "The 2-year futures row is a labeled proxy, not the cash 2-year Treasury yield.",
            "Stale or delayed quotes stay labeled and do not receive an implied current-session move.",
            "Calendar items and catalysts are context only; they are not presented as causes of market moves.",
            "The Morning Tape is a pre-market orientation, not a forecast or trading recommendation.",
        ],
    }

    payload = json.dumps(snapshot, indent=2) + "\n"
    for filename in (snapshot_path, public_path):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    print(f"Morning Tape written to {snapshot_path} and {public_path}")
    return snapshot


if __name__ == "__main__":
    generate_morning_snapshot()
