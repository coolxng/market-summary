import datetime
import json
import tempfile
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=None))

import generate_morning
import offline_fixtures


class FakeColumn:
    def __init__(self, values):
        self.values = values
        self.iloc = self

    def __getitem__(self, position):
        return self.values[position]


class FakeHistory:
    def __init__(self, index, closes):
        self.index = index
        self.closes = closes

    def __len__(self):
        return len(self.closes)

    def __getitem__(self, key):
        if key != "Close":
            raise KeyError(key)
        return FakeColumn(self.closes)

    def dropna(self, subset=None):
        return self


class FakeTicker:
    def __init__(self, daily, intraday):
        self.daily = daily
        self.intraday = intraday

    def history(self, period, interval, **kwargs):
        return self.daily if interval == "1d" else self.intraday


class GenerateMorningTests(unittest.TestCase):
    def test_latest_quote_uses_last_completed_daily_close(self):
        daily = FakeHistory(
            [
                datetime.datetime(2026, 9, 18, 16, 0, tzinfo=generate_morning.NY_TZ),
                datetime.datetime(2026, 9, 21, 16, 0, tzinfo=generate_morning.NY_TZ),
            ],
            [100.0, 110.0],
        )
        intraday = FakeHistory(
            [datetime.datetime(2026, 9, 22, 8, 40, tzinfo=generate_morning.NY_TZ)],
            [111.0],
        )
        now = datetime.datetime(2026, 9, 22, 7, 45, tzinfo=generate_morning.NY_TZ)

        with mock.patch.object(generate_morning.yf, "Ticker", return_value=FakeTicker(daily, intraday)):
            result = generate_morning.latest_quote("ES=F", now)

        self.assertEqual(result["reference_close"], 110.0)
        self.assertEqual(result["reference_date"], "2026-09-21")
        self.assertEqual(result["pct_change"], 0.91)
        self.assertFalse(result["stale"])

    def test_daily_only_quote_is_marked_stale_instead_of_implying_current_move(self):
        daily = FakeHistory(
            [
                datetime.datetime(2026, 9, 18, 16, 0, tzinfo=generate_morning.NY_TZ),
                datetime.datetime(2026, 9, 21, 16, 0, tzinfo=generate_morning.NY_TZ),
            ],
            [100.0, 110.0],
        )
        intraday = FakeHistory([], [])
        now = datetime.datetime(2026, 9, 22, 7, 45, tzinfo=generate_morning.NY_TZ)

        with mock.patch.object(generate_morning.yf, "Ticker", return_value=FakeTicker(daily, intraday)):
            result = generate_morning.latest_quote("^FTSE", now)

        self.assertEqual(result["price"], 110.0)
        self.assertIsNone(result["pct_change"])
        self.assertTrue(result["stale"])

    def test_old_intraday_bar_is_marked_delayed(self):
        daily = FakeHistory([datetime.datetime(2026, 9, 21, 16, 0, tzinfo=generate_morning.NY_TZ)], [110.0])
        intraday = FakeHistory([datetime.datetime(2026, 9, 22, 4, 0, tzinfo=generate_morning.NY_TZ)], [111.0])
        now = datetime.datetime(2026, 9, 22, 8, 45, tzinfo=generate_morning.NY_TZ)
        with mock.patch.object(generate_morning.yf, "Ticker", return_value=FakeTicker(daily, intraday)):
            result = generate_morning.latest_quote("ES=F", now, freshness_limit_minutes=90)
        self.assertEqual(result["age_minutes"], 285)
        self.assertTrue(result["delayed"])


def quote(name, pct, region=None, **extra):
    return {"name": name, "symbol": name, "pct_change": pct, "reference_date": "2026-09-21",
            "stale": False, "delayed": False, "error": None, "region": region, **extra}


class WhatMattersTodayTests(unittest.TestCase):
    def test_observed_bullets_skip_delayed_quotes_and_cite_dates(self):
        futures = {"ES=F": quote("S&P 500 E-mini futures", 0.4), "NQ=F": quote("Nasdaq 100 E-mini futures", 0.9),
                   "RTY=F": quote("Russell 2000 E-mini futures", -3.0, delayed=True)}
        global_markets = {"^N225": quote("Nikkei 225", -0.5, "Asia"), "^FTSE": quote("FTSE 100", None, "Europe")}
        calendar = {"items": [
            {"date": "2026-09-22", "kind": "economic", "time": "7:30 AM CT", "title": "CPI (YoY)"},
            {"date": "2026-09-22", "kind": "economic", "time": "9:00 AM CT", "title": "Home Sales"},
            {"date": "2026-09-22", "kind": "earnings", "ticker": "MU", "title": "MU earnings"},
            {"date": "2026-09-23", "kind": "economic", "time": "7:30 AM CT", "title": "Claims"},
        ]}
        catalysts = {"items": [{"title": "FOMC statement", "publisher": "Federal Reserve"}]}
        rates = {"curve": {"as_of": "2026-09-21", "tenors": {"10y": {"value": 3.95}}}, "spreads": {"2s10s": {"value_bp": 40.0}}}
        items = generate_morning.what_matters_today(datetime.date(2026, 9, 22), futures, global_markets, calendar, catalysts, rates)
        text = {item["label"]: item["text"] for item in items}
        self.assertEqual(len(items), 5)
        self.assertIn("S&P 500 E-mini futures +0.40% versus the Sep 21 daily close", text["Futures"])
        self.assertIn("Nasdaq 100 E-mini futures +0.90%", text["Futures"])
        self.assertNotIn("Russell", text["Futures"])
        self.assertEqual(text["Overnight"], "Nikkei 225 -0.50%.")
        self.assertEqual(text["Calendar"], "CPI (YoY) at 7:30 AM CT and 1 more scheduled U.S. release.")
        self.assertIn("MU", text["Earnings"])
        self.assertEqual(text["Rates"], "Official 10-year Treasury 3.95% as of Sep 21; 2s10s +40 bps.")

    def test_no_data_yields_no_bullets(self):
        empty = {"items": []}
        self.assertEqual(generate_morning.what_matters_today(datetime.date(2026, 9, 22), {}, {}, empty, empty, None), [])


class MorningSnapshotTests(unittest.TestCase):
    def test_snapshot_is_written_offline_with_feed_health(self):
        now = datetime.datetime(2026, 9, 22, 8, 45, tzinfo=generate_morning.NY_TZ)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(generate_morning, "latest_quote", side_effect=lambda symbol, *_: {"symbol": symbol, "price": 1.0, "pct_change": 0.1, "reference_date": "2026-09-21", "stale": False, "delayed": False, "error": None}), \
                mock.patch.object(generate_morning, "build_market_calendar", side_effect=offline_fixtures.offline_market_calendar), \
                mock.patch.object(generate_morning, "build_verified_catalysts", side_effect=offline_fixtures.offline_catalysts), \
                mock.patch.object(generate_morning, "fetch_treasury_rates", return_value={"id": "treasury_curve", "name": "Treasury", "source_url": "https://t", "status": "unavailable", "as_of": None, "error": "x", "curve": None, "spreads": {}, "real": None}):
            snapshot = generate_morning.generate_morning_snapshot(now, f"{tmp}/m.json", f"{tmp}/public/latest.json")
            self.assertEqual(json.loads(Path(f"{tmp}/public/latest.json").read_text()), snapshot)
        self.assertEqual(snapshot["market_date"], "2026-09-22")
        self.assertEqual(snapshot["previous_session"], "2026-09-21")
        self.assertEqual(snapshot["status"], "ready")
        self.assertIn("ETH-USD", snapshot["cross_asset"])
        self.assertTrue(snapshot["cross_asset"]["2YY=F"]["proxy"])
        self.assertIn("treasury_curve", [feed["id"] for feed in snapshot["data_quality"]["feeds"]])


if __name__ == "__main__":
    unittest.main()
