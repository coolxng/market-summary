import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

from market_intelligence import fetch_economic_calendar, fetch_market_headlines, fetch_tracked_earnings


NY_TZ = ZoneInfo("America/New_York")
TRACKED_EARNINGS = ("AAPL", "MSFT", "NVDA", "AMZN", "META", "AMD", "INTC", "MU", "SNDK")

FUTURES = {
    "ES=F": "S&P 500 Futures",
    "NQ=F": "Nasdaq 100 Futures",
    "YM=F": "Dow Futures",
    "RTY=F": "Russell 2000 Futures",
}

CROSS_ASSET = {
    "^VIX": "VIX",
    "^MOVE": "MOVE Index",
    "2YY=F": "2-Year Yield Futures (proxy)",
    "^TNX": "10-Year Yield",
    "DX-Y.NYB": "U.S. Dollar Index",
    "GC=F": "Gold",
    "CL=F": "WTI Crude",
    "BTC-USD": "Bitcoin",
}

GLOBAL = {
    "^N225": "Nikkei 225",
    "^STOXX50E": "Euro Stoxx 50",
    "^FTSE": "FTSE 100",
    "^HSI": "Hang Seng",
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


def latest_quote(symbol, now=None):
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
            latest_date = _bar_date(timestamp)
        else:
            latest = float(daily["Close"].iloc[-1])
            timestamp = daily.index[-1]
            latest_date = _bar_date(timestamp)

        stale = not has_intraday and latest_date < current.date()
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        if isinstance(timestamp, datetime.datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=NY_TZ)
            timestamp = timestamp.astimezone(NY_TZ).isoformat()
        else:
            timestamp = str(timestamp)

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
            "stale": stale,
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
            "stale": False,
            "source": "Yahoo Finance via yfinance",
            "error": "quote unavailable",
        }


def generate_morning_snapshot(now=None, snapshot_path="morning_snapshot.json", public_path="public/morning/latest.json"):
    current = market_now(now)
    market_date = current.date()

    print(f"Building Morning Tape for {market_date.isoformat()}...")
    futures = {
        symbol: {"name": name, **latest_quote(symbol, current)}
        for symbol, name in FUTURES.items()
    }
    cross_asset = {
        symbol: {"name": name, **latest_quote(symbol, current)}
        for symbol, name in CROSS_ASSET.items()
    }
    global_markets = {
        symbol: {"name": name, **latest_quote(symbol, current)}
        for symbol, name in GLOBAL.items()
    }

    economic = fetch_economic_calendar(market_date, days=3, max_items=12)
    earnings = fetch_tracked_earnings(TRACKED_EARNINGS, market_date, days=5, max_items=10)
    headlines = fetch_market_headlines(
        market_date,
        queries=("stock market", "Federal Reserve", "Treasury yields", "technology stocks"),
        max_items=6,
    )

    all_quotes = [*futures.values(), *cross_asset.values(), *global_markets.values()]
    valid = sum(
        1 for quote in all_quotes
        if not quote.get("error") and not quote.get("stale") and quote.get("price") is not None
    )
    coverage = round(valid / len(all_quotes) * 100, 1) if all_quotes else 0.0

    valid_futures = [
        quote for quote in futures.values()
        if quote.get("pct_change") is not None and not quote.get("stale")
    ]
    what_matters_today = []
    if valid_futures:
        leading_future = max(valid_futures, key=lambda quote: abs(quote["pct_change"]))
        what_matters_today.append(
            f'{leading_future["name"]}: {leading_future["pct_change"]:+.2f}% versus the {leading_future["reference_date"]} reference close.'
        )
    economic_items = economic.get("items") or []
    if economic_items:
        first_event = economic_items[0]
        what_matters_today.append(
            f'Calendar: {first_event.get("title", "scheduled release")} at {first_event.get("time", "TBD")}.'
        )
    headline_items = headlines.get("items") or []
    if headline_items:
        first_headline = headline_items[0]
        what_matters_today.append(
            f'Source-linked: {first_headline["title"]} — {first_headline["publisher"]}.'
        )

    snapshot = {
        "report_type": "morning_tape",
        "market_date": market_date.isoformat(),
        "generated_at": current.isoformat(),
        "status": "ready" if coverage >= 80 else "partial",
        "data_quality": {
            "valid": valid,
            "total": len(all_quotes),
            "coverage_pct": coverage,
        },
        "futures": futures,
        "cross_asset": cross_asset,
        "global_markets": global_markets,
        "market_calendar": {
            "economic": economic,
            "earnings": earnings,
        },
        "market_headlines": headlines,
        "what_matters_today": what_matters_today,
        "notes": [
            "Futures and extended-hours moves are compared with the latest completed daily reference close.",
            "The 2-Year reading is a Yahoo Finance yield-futures proxy, not the cash 2-Year Treasury yield.",
            "Stale feeds remain labeled and do not receive an implied current-session percentage move.",
            "Calendar items and headlines are context only; they are not presented as causes of market moves.",
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
