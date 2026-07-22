import datetime
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=None))

import generate_report


class FakeColumn:
    def __init__(self, values):
        self.values = values
        self.iloc = self

    def __getitem__(self, position):
        return self.values[position]


class FakeHistory:
    def __init__(self, index, rows):
        self.index = index
        self.rows = rows
        self.iloc = self

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.rows[key]
        return FakeColumn([row[key] for row in self.rows])

    def dropna(self, subset=None):
        return self


def valid_dataset(symbol, session_date, previous_session_date):
    prices = {
        "^GSPC": 6000.0,
        "^IXIC": 19000.0,
        "^DJI": 42000.0,
        "^RUT": 2100.0,
        "^VIX": 20.0,
        "^TNX": 4.2,
        "^IRX": 4.0,
        "DX-Y.NYB": 102.0,
        "GC=F": 2400.0,
        "CL=F": 75.0,
        "BTC-USD": 70000.0,
        "ETH-USD": 3500.0,
        "SOL-USD": 160.0,
        "XRP-USD": 0.75,
        "^N225": 41000.0,
        "^STOXX50E": 5200.0,
        "^FTSE": 8500.0,
        "^HSI": 22000.0,
    }
    end_price = prices.get(symbol, 100.0)
    prev_close = round(end_price / 1.01, 2)
    return {
        "dates": [previous_session_date.isoformat(), session_date.isoformat()],
        "closes": [prev_close, end_price],
        "end_price": end_price,
        "pct_change": round(((end_price - prev_close) / prev_close) * 100, 2),
        "abs_change": round(end_price - prev_close, 2),
        "prev_close": prev_close,
        "session_open": round(prev_close * 1.002, 2),
        "day_high": round(end_price * 1.002, 2),
        "day_low": round(prev_close * 0.998, 2),
        "session_date": session_date.isoformat(),
        "previous_session_date": previous_session_date.isoformat(),
        "ticker_used": symbol,
        "error": None,
    }


class GenerateReportTests(unittest.TestCase):
    def test_normal_tuesday_after_close_selects_tuesday(self):
        now = datetime.datetime(2026, 7, 14, 17, 30, tzinfo=generate_report.NY_TZ)
        session, previous = generate_report.resolve_completed_sessions(
            now,
            session_dates=[datetime.date(2026, 7, 10), datetime.date(2026, 7, 13), datetime.date(2026, 7, 14)],
        )
        self.assertEqual(session, datetime.date(2026, 7, 14))
        self.assertEqual(previous, datetime.date(2026, 7, 13))

    def test_monday_after_close_compares_with_friday(self):
        now = datetime.datetime(2026, 7, 13, 17, 30, tzinfo=generate_report.NY_TZ)
        session, previous = generate_report.resolve_completed_sessions(
            now,
            session_dates=[datetime.date(2026, 7, 9), datetime.date(2026, 7, 10), datetime.date(2026, 7, 13)],
        )
        self.assertEqual(session, datetime.date(2026, 7, 13))
        self.assertEqual(previous, datetime.date(2026, 7, 10))

    def test_weekend_execution_uses_friday(self):
        now = datetime.datetime(2026, 7, 18, 12, 0, tzinfo=generate_report.NY_TZ)
        self.assertEqual(generate_report.latest_completed_session_candidate(now), datetime.date(2026, 7, 17))

    def test_holiday_or_missing_session_uses_latest_available_bar(self):
        now = datetime.datetime(2026, 7, 3, 17, 30, tzinfo=generate_report.NY_TZ)
        session, previous = generate_report.resolve_completed_sessions(
            now,
            session_dates=[datetime.date(2026, 7, 1), datetime.date(2026, 7, 2)],
        )
        self.assertEqual(session, datetime.date(2026, 7, 2))
        self.assertEqual(previous, datetime.date(2026, 7, 1))

    def test_pre_close_run_uses_previous_completed_session(self):
        now = datetime.datetime(2026, 7, 14, 15, 59, tzinfo=generate_report.NY_TZ)
        self.assertEqual(generate_report.latest_completed_session_candidate(now), datetime.date(2026, 7, 13))

    def test_dst_and_standard_time_are_converted_to_new_york(self):
        utc = datetime.timezone.utc
        summer = datetime.datetime(2026, 7, 14, 21, 30, tzinfo=utc)
        winter = datetime.datetime(2026, 1, 13, 21, 30, tzinfo=utc)
        self.assertEqual(generate_report.latest_completed_session_candidate(summer), datetime.date(2026, 7, 14))
        self.assertEqual(generate_report.latest_completed_session_candidate(winter), datetime.date(2026, 1, 13))

    def test_daily_change_uses_immediately_preceding_session_close(self):
        history = FakeHistory(
            [datetime.date(2026, 7, 10), datetime.date(2026, 7, 13), datetime.date(2026, 7, 14)],
            [
                {"Open": 99.0, "High": 101.0, "Low": 98.0, "Close": 100.0},
                {"Open": 102.0, "High": 104.0, "Low": 101.0, "Close": 103.0},
                {"Open": 104.0, "High": 106.0, "Low": 103.0, "Close": 105.0},
            ],
        )
        ticker = types.SimpleNamespace(history=lambda **kwargs: history)
        with mock.patch.object(generate_report.yf, "Ticker", return_value=ticker):
            result = generate_report.fetch_daily_data(
                "TEST",
                datetime.date(2026, 7, 14),
                datetime.date(2026, 7, 13),
            )
        self.assertEqual(result["prev_close"], 103.0)
        self.assertEqual(result["end_price"], 105.0)
        self.assertEqual(result["pct_change"], 1.94)
        self.assertEqual(result["day_high"], 106.0)
        self.assertEqual(result["day_low"], 103.0)

    def test_session_chart_excludes_premarket_and_after_hours(self):
        times = [
            datetime.datetime(2026, 7, 14, 9, 0, tzinfo=generate_report.NY_TZ),
            datetime.datetime(2026, 7, 14, 9, 30, tzinfo=generate_report.NY_TZ),
            datetime.datetime(2026, 7, 14, 12, 0, tzinfo=generate_report.NY_TZ),
            datetime.datetime(2026, 7, 14, 16, 0, tzinfo=generate_report.NY_TZ),
            datetime.datetime(2026, 7, 14, 16, 30, tzinfo=generate_report.NY_TZ),
        ]
        history = FakeHistory(times, [{"Close": value} for value in (99, 100, 102, 103, 104)])
        ticker = types.SimpleNamespace(history=lambda **kwargs: history)
        with mock.patch.object(generate_report.yf, "Ticker", return_value=ticker):
            chart = generate_report.fetch_daily_chart_data("^GSPC", datetime.date(2026, 7, 14))
        self.assertEqual(chart["closes"], [100.0, 102.0, 103.0])
        self.assertEqual(chart["times"], ["9:30 AM", "12:00 PM", "4:00 PM"])
        self.assertEqual(chart["source"], "intraday_5m")

    def test_render_html_with_strong_escapes_other_markup(self):
        raw = '<script>alert(1)</script><strong>Leader</strong>'
        sanitized = generate_report.render_html_with_strong(raw)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", sanitized)
        self.assertIn("<strong>Leader</strong>", sanitized)

    def test_preserve_premium_shell_replaces_body_and_title(self):
        legacy = "<title>Old</title><style>body { color: black; }</style><body>old</body>"
        self.assertIsNone(generate_report.preserve_premium_shell(legacy, "New", "<main>new</main>"))
        premium = legacy.replace("<style>", f"<style>/* {generate_report.PREMIUM_DESIGN_MARKER} */")
        rendered = generate_report.preserve_premium_shell(premium, "New & Safe", "<main>new</main>")
        self.assertIn("<title>New &amp; Safe</title>", rendered)
        self.assertIn("<main>new</main>", rendered)

    def test_nikkei_sanity_bound_accepts_current_index_levels(self):
        self.assertTrue(generate_report.is_sane("^N225", 64141.12))

    def test_validate_dataset_rejects_zeroed_core_data(self):
        with self.assertRaisesRegex(ValueError, "end price is invalid"):
            generate_report.validate_dataset(
                {"end_price": 0.0, "closes": [0.0], "ticker_used": "^GSPC", "error": None},
                "^GSPC",
            )

    def test_generated_daily_schema_html_and_session_dates_agree(self):
        session = datetime.date(2026, 7, 14)
        previous = datetime.date(2026, 7, 13)

        def fake_fetch(symbol, session_date, previous_session_date=None):
            return valid_dataset(symbol, session_date, previous_session_date or previous)

        def fake_chart(symbol, session_date, fallback_data=None):
            return {
                "times": ["9:30 AM", "12:00 PM", "4:00 PM"],
                "closes": [fallback_data["session_open"], fallback_data["day_high"], fallback_data["end_price"]],
                "source": "intraday_5m",
                "session_date": session_date.isoformat(),
                "error": None,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "report_snapshot.json"
            report_path = Path(temp_dir) / "daily-report.html"
            with (
                mock.patch.object(generate_report, "resolve_completed_sessions", return_value=(session, previous)),
                mock.patch.object(generate_report, "fetch_daily_data", side_effect=fake_fetch),
                mock.patch.object(generate_report, "fetch_daily_chart_data", side_effect=fake_chart),
                mock.patch.object(generate_report, "should_use_ai", return_value=False),
            ):
                changed = generate_report.generate_html(
                    now=datetime.datetime(2026, 7, 14, 17, 30, tzinfo=generate_report.NY_TZ),
                    snapshot_path=snapshot_path,
                    report_path=report_path,
                )

            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            rendered = report_path.read_text(encoding="utf-8")
            self.assertTrue(changed)
            self.assertEqual(snapshot["report_type"], "daily_market_close")
            self.assertEqual(snapshot["session_date"], "2026-07-14")
            self.assertEqual(snapshot["previous_session_date"], "2026-07-13")
            self.assertEqual(snapshot["market_data"]["^GSPC"]["session_date"], snapshot["session_date"])
            self.assertGreater(snapshot["market_data"]["^GSPC"]["end_price"], 0)
            self.assertIn("daily_sector_performance", snapshot)
            self.assertIn("daily_market_breadth", snapshot)
            self.assertNotIn("report_window", snapshot)
            self.assertNotIn("hourly_charts", snapshot)
            self.assertIn("Daily Market Summary", rendered)
            self.assertIn("Daily Market Close", rendered)
            self.assertNotRegex(rendered, r"(?i)weekly|\bWTD\b|week_high|week_low")

    def test_same_session_does_not_overwrite_artifacts(self):
        session = datetime.date(2026, 7, 14)
        previous = datetime.date(2026, 7, 13)
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "report_snapshot.json"
            report_path = Path(temp_dir) / "daily-report.html"
            snapshot_path.write_text(json.dumps({"report_type": "daily_market_close", "session_date": session.isoformat()}), encoding="utf-8")
            report_path.write_text("unchanged", encoding="utf-8")
            with (
                mock.patch.object(generate_report, "resolve_completed_sessions", return_value=(session, previous)),
                mock.patch.object(generate_report, "fetch_daily_data") as fetch_mock,
            ):
                changed = generate_report.generate_html(snapshot_path=snapshot_path, report_path=report_path)
            self.assertFalse(changed)
            fetch_mock.assert_not_called()
            self.assertEqual(report_path.read_text(encoding="utf-8"), "unchanged")


if __name__ == "__main__":
    unittest.main()
