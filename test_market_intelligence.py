import datetime
import sys
import types
import unittest

sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=None))

import market_intelligence  # noqa: E402


def row(session, price=100.0, error=None):
    return {"session_date": session, "end_price": price, "error": error, "data_source": "yahoo_finance"}


class DataQualityTests(unittest.TestCase):
    session = datetime.date(2026, 9, 21)

    def test_full_coverage_and_healthy_feeds_are_verified(self):
        quality = market_intelligence.build_data_quality(
            {"^GSPC": row("2026-09-21")},
            self.session,
            feed_groups=([{"name": "Calendar", "status": "ok"}], [{"name": "News", "status": "empty"}]),
        )
        self.assertEqual(quality["status"], "healthy")
        self.assertEqual(quality["overall"], "verified")
        self.assertEqual(quality["unavailable_feeds"], [])

    def test_unavailable_feed_makes_status_partial(self):
        quality = market_intelligence.build_data_quality(
            {"^GSPC": row("2026-09-21")},
            self.session,
            feed_groups=([{"name": "Nasdaq Economic Calendar", "status": "unavailable"}],),
        )
        self.assertEqual(quality["overall"], "partial")
        self.assertEqual(quality["unavailable_feeds"], ["Nasdaq Economic Calendar"])

    def test_stale_and_missing_rows_are_flagged(self):
        quality = market_intelligence.build_data_quality(
            {
                "^GSPC": row("2026-09-21"),
                "GC=F": row("2026-09-18"),
                "CL=F": row(None, price=None, error="Data unavailable for CL=F"),
            },
            self.session,
        )
        self.assertEqual(quality["valid"], 1)
        self.assertIn("GC=F: stale session 2026-09-18", quality["issues"])
        self.assertIn("CL=F: unavailable", quality["issues"])
        self.assertEqual(quality["overall"], "limited")

    def test_other_calendars_record_local_session_instead_of_stale(self):
        quality = market_intelligence.build_data_quality(
            {"^GSPC": row("2026-09-21"), "^N225": row("2026-09-18"), "BTC-USD": row("2026-09-20"), "^FTSE": row("2026-09-10")},
            self.session,
            local_calendar_symbols=("^N225", "BTC-USD", "^FTSE"),
            previous_session=datetime.date(2026, 9, 18),
        )
        self.assertEqual(quality["local_sessions"], {"^N225": "2026-09-18", "BTC-USD": "2026-09-20"})
        self.assertEqual(quality["issues"], ["^FTSE: stale session 2026-09-10"])
        self.assertEqual(quality["valid"], 3)

    def test_multi_day_overseas_holiday_is_not_stale(self):
        # Tokyo was shut Sep 21-23, 2026, so the Sep 22 report sees a Sep 18 Nikkei close.
        quality = market_intelligence.build_data_quality(
            {"^GSPC": row("2026-09-22"), "^N225": row("2026-09-18")},
            datetime.date(2026, 9, 22),
            local_calendar_symbols=("^N225",),
            previous_session=datetime.date(2026, 9, 21),
        )
        self.assertEqual(quality["local_sessions"], {"^N225": "2026-09-18"})
        self.assertEqual(quality["issues"], [])
        self.assertEqual(quality["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
