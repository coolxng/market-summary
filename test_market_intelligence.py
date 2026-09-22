import datetime
import types
import unittest
from unittest import mock

import market_intelligence


class MarketIntelligenceTests(unittest.TestCase):
    def test_calendar_gmt_time_is_normalized_to_central(self):
        event = market_intelligence._calendar_event(
            {
                "eventName": "CPI",
                "gmt": "13:30:00",
                "country": "United States",
                "actual": "2.7%",
                "consensus": "2.8%",
                "previous": "2.9%",
            },
            datetime.date(2026, 9, 22),
        )
        self.assertEqual(event["time"], "8:30 AM CT")
        self.assertEqual(event["time_zone"], "America/Chicago")
        self.assertEqual(event["category"], "Economic data")
        self.assertEqual(event["source_url"], market_intelligence.NASDAQ_CALENDAR_PAGE)

    def test_calendar_preserves_source_importance_without_inventing_one(self):
        event = market_intelligence._calendar_event(
            {"eventName": "Claims", "time": "8:30 AM", "importance": "High"},
            datetime.date(2026, 9, 22),
        )
        self.assertEqual(event["importance"], "High")

        event_without_importance = market_intelligence._calendar_event(
            {"eventName": "Claims", "time": "8:30 AM"},
            datetime.date(2026, 9, 22),
        )
        self.assertIsNone(event_without_importance["importance"])

    @mock.patch.object(market_intelligence, "_runtime_data_available", return_value=True)
    @mock.patch.object(market_intelligence, "_yahoo_news_via_http", return_value=[])
    @mock.patch.object(market_intelligence, "_yahoo_news_via_search")
    def test_headline_feed_omits_unapproved_publishers(self, search, _http, _runtime):
        close = datetime.datetime(2026, 9, 22, 16, 0, tzinfo=market_intelligence.NY_TZ)
        timestamp = int(close.timestamp())
        search.return_value = [
            {
                "title": "Reuters development",
                "link": "https://example.com/reuters",
                "publisher": "Reuters",
                "providerPublishTime": timestamp,
                "relatedTickers": ["SPY"],
            },
            {
                "title": "Random blog claim",
                "link": "https://example.com/blog",
                "publisher": "Random Finance Blog",
                "providerPublishTime": timestamp,
            },
        ]
        result = market_intelligence.fetch_market_headlines(
            datetime.date(2026, 9, 22),
            queries=("stock market",),
            max_items=6,
        )
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["publisher"], "Reuters")
        self.assertEqual(result["items"][0]["affected_assets"], ["SPY"])


if __name__ == "__main__":
    unittest.main()
