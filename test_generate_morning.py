import datetime
import sys
import types
import unittest
from unittest import mock

sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=None))

import generate_morning


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


if __name__ == "__main__":
    unittest.main()
