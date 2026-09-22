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


def latest_quote(symbol):
    """Return the latest extended-hours/futures quote against the prior daily close."""
    try:
        ticker = yf.Ticker(symbol)
        daily = ticker.history(period="5d", interval="1d", auto_adjust=False).dropna(subset=["Close"])
        intraday = ticker.history(period="2d", interval="5m", prepost=True, auto_adjust=False).dropna(subset=["Close"])
        if len(daily) < 2:
            raise ValueError("insufficient daily bars")
        reference = float(daily["Close"].iloc[-2])
        latest = float(intraday["Close"].iloc[-1]) if len(intraday) else float(daily["Close"].iloc[-1])
        timestamp = intraday.index[-1] if len(intraday) else daily.index[-1]
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        if isinstance(timestamp, datetime.datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=NY_TZ)
            timestamp = timestamp.astimezone(NY_TZ).isoformat()
        else:
            timestamp = str(timestamp)
        pct = ((latest - reference) / reference) * 100 if reference else 0.0
        return {
            "symbol": symbol,
            "price": round(latest, 4),
            "reference_close": round(reference, 4),
            "pct_change": round(pct, 2),
            "timestamp": timestamp,
            "source": "Yahoo Finance via yfinance",
            "error": None,
        }
    except Exception as exc:
        print(f"  Morning quote unavailable for {symbol}: {exc}")
        return {
            "symbol": symbol,
            "price": None,
            "reference_close": None,
            "pct_change": None,
            "timestamp": None,
            "source": "Yahoo Finance via yfinance",
            "error": "quote unavailable",
        }


def generate_morning_snapshot(now=None, snapshot_path="morning_snapshot.json", public_path="public/morning/latest.json"):
    current = market_now(now)
    market_date = current.date()

    print(f"Building Morning Tape for {market_date.isoformat()}...")
    futures = {
        symbol: {"name": name, **latest_quote(symbol)}
        for symbol, name in FUTURES.items()
    }
    cross_asset = {
        symbol: {"name": name, **latest_quote(symbol)}
        for symbol, name in CROSS_ASSET.items()
    }
    global_markets = {
        symbol: {"name": name, **latest_quote(symbol)}
        for symbol, name in GLOBAL.items()
    }

    economic = fetch_economic_calendar(market_date, days=3, max_items=12)
    earnings = fetch_tracked_earnings(TRACKED_EARNINGS, market_date, days=5, max_items=10)
    headlines = fetch_market_headlines(
        market_date,
        queries=("stock market", "Federal Reserve", "Treasury yields", "technology stocks"),
        max_items=8,
    )

    all_quotes = [*futures.values(), *cross_asset.values(), *global_markets.values()]
    valid = sum(1 for quote in all_quotes if not quote.get("error") and quote.get("price") is not None)
    coverage = round(valid / len(all_quotes) * 100, 1) if all_quotes else 0.0

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
        "notes": [
            "Futures and extended-hours moves are compared with the prior available daily close.",
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
