"""Deterministic offline fixtures for tests.

Nothing here is ever written into committed report artifacts. The generator's
external feeds (history, calendar, catalysts, official rates) are patched with
these fakes so the unit suite never touches the network, including when
railway_cron.py runs it inside the production image where the real yfinance
package is installed.
"""

import contextlib
import datetime
import math
from unittest import mock

import data_providers


def business_days_ending(end, count):
    days = []
    day = end
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= datetime.timedelta(days=1)
    return list(reversed(days))


def synthetic_history(symbol, session_date, final_close=100.0, count=260, dividends=None):
    """Smooth deterministic path that ends exactly at `final_close`."""
    days = business_days_ending(session_date, count)
    seed = sum(ord(character) for character in symbol)
    raw = [1 + 0.08 * math.sin((index + seed) / 9) + 0.0006 * index for index in range(count)]
    scale = final_close / raw[-1]
    closes = [round(value * scale, 4) for value in raw]
    return {
        "symbol": symbol,
        "dates": [day.isoformat() for day in days],
        "closes": closes,
        "dividends": dividends or {},
        "returns": {"5d": 0.5, "1m": 1.0, "3m": 2.0, "ytd": 3.0, "1y": 4.0},
        "moving_averages": {"20d": closes[-1], "50d": closes[-1], "200d": closes[-1]},
        "above_moving_average": {"20d": True, "50d": False, "200d": True},
        "source": "Yahoo Finance via yfinance",
        "as_of": days[-1].isoformat(),
        "error": None,
    }


def empty_feed(feed_id, name):
    return data_providers.feed_result(feed_id, name, "https://example.invalid/", status="disabled", error="Offline test run.")


def offline_market_calendar(anchor, _tickers, **_kwargs):
    return data_providers.build_market_calendar(
        anchor,
        (),
        providers=(lambda days: empty_feed("nasdaq_economic", "Nasdaq Economic Calendar"),),
    )


def offline_catalysts(start, end, **_kwargs):
    return data_providers.build_verified_catalysts(
        start,
        end,
        providers=[lambda s, e: empty_feed("yahoo_news", "Yahoo Finance news search")],
    )


@contextlib.contextmanager
def offline_generation(module, price_lookup=None):
    """Patch every networked feed the report generator uses."""
    price_lookup = price_lookup or (lambda symbol: 100.0)

    def history_bundle(symbols, session_date):
        return {symbol: synthetic_history(symbol, session_date, price_lookup(symbol)) for symbol in dict.fromkeys(symbols)}

    patches = [
        mock.patch.object(module, "fetch_history_bundle", side_effect=history_bundle),
        mock.patch.object(module, "build_market_calendar", side_effect=offline_market_calendar),
        mock.patch.object(module, "build_verified_catalysts", side_effect=offline_catalysts),
    ]
    with contextlib.ExitStack() as stack:
        for patch in patches:
            stack.enter_context(patch)
        yield
