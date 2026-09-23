import datetime
import json
import os
import unittest
from unittest import mock

import data_providers
import trading_calendar

NY = data_providers.NY_TZ


def ts(year, month, day, hour, minute=0):
    return int(datetime.datetime(year, month, day, hour, minute, tzinfo=NY).timestamp())


RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Fed</title>
<item><title>Federal Reserve issues FOMC statement</title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm</link>
<pubDate>Wed, 16 Sep 2026 18:00:00 GMT</pubDate></item>
<item><title>Older release</title>
<link>https://www.federalreserve.gov/old.htm</link>
<pubDate>Mon, 07 Sep 2026 18:00:00 GMT</pubDate></item>
<item><title>No timestamp</title><link>https://www.federalreserve.gov/x.htm</link></item>
<item><title>Insecure</title><link>http://example.com/x</link><pubDate>Wed, 16 Sep 2026 18:00:00 GMT</pubDate></item>
</channel></rss>"""


class TradingCalendarTests(unittest.TestCase):
    def test_published_nyse_holidays(self):
        self.assertEqual(
            sorted(day.isoformat() for day in trading_calendar.nyse_holidays(2026)),
            ["2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
             "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"],
        )

    def test_saturday_new_year_is_not_observed_on_friday(self):
        self.assertNotIn(datetime.date(2021, 12, 31), trading_calendar.nyse_holidays(2021))
        self.assertNotIn(datetime.date(2022, 1, 1), trading_calendar.nyse_holidays(2022))
        self.assertTrue(trading_calendar.is_trading_day(datetime.date(2021, 12, 31)))

    def test_session_window_skips_weekend_and_holiday(self):
        # Friday before Labor Day 2026: next session is Tuesday.
        self.assertEqual(
            trading_calendar.session_window(datetime.date(2026, 9, 4)),
            [datetime.date(2026, 9, 4), datetime.date(2026, 9, 8)],
        )
        # A Saturday anchor has no current session.
        self.assertEqual(trading_calendar.session_window(datetime.date(2026, 9, 19)), [datetime.date(2026, 9, 21)])

    def test_expiration_moves_to_thursday_on_good_friday(self):
        # Good Friday 2025 fell on the third Friday of April.
        self.assertEqual(trading_calendar.monthly_options_expiration(2025, 4), datetime.date(2025, 4, 17))
        self.assertEqual(trading_calendar.monthly_options_expiration(2026, 9), datetime.date(2026, 9, 18))

    def test_market_structure_events_are_labeled_rule_based(self):
        events = trading_calendar.market_structure_events([datetime.date(2026, 11, 25), datetime.date(2026, 11, 27)])
        titles = [event["title"] for event in events]
        self.assertTrue(any("closed (Thanksgiving Day)" in title for title in titles))
        self.assertTrue(any(title.startswith("Early close") for title in titles))
        self.assertTrue(all(event["rule_based"] for event in events))


class CalendarProviderTests(unittest.TestCase):
    def test_fair_economy_rows_use_embedded_timestamp_for_date_and_time(self):
        rows = [
            {"title": "FOMC Member Goolsbee Speaks", "country": "USD",
             "date": "2026-09-21T06:30:00-04:00", "impact": "Low", "forecast": "", "previous": ""},
            {"title": "Richmond Manufacturing Index", "country": "USD",
             "date": "2026-09-22T10:00:00-04:00", "impact": "Low", "forecast": "2", "previous": "4"},
            {"title": "ECB Rate Decision", "country": "EUR",
             "date": "2026-09-22T08:15:00-04:00", "impact": "High"},
            {"title": "Bank Holiday", "country": "USD",
             "date": "2026-09-22T19:00:00-04:00", "impact": "Holiday"},
        ]
        days = [datetime.date(2026, 9, 21), datetime.date(2026, 9, 22)]
        items = data_providers.parse_fair_economy_rows(rows, days)
        self.assertEqual([item["title"] for item in items],
                         ["FOMC Member Goolsbee Speaks", "Richmond Manufacturing Index"])
        goolsbee = items[0]
        self.assertEqual(goolsbee["date"], "2026-09-21")
        self.assertEqual(goolsbee["time"], "5:30 AM CT")
        self.assertEqual(goolsbee["source_time"], "6:30 AM")
        self.assertEqual(goolsbee["source_time_zone"], "ET")
        self.assertEqual(goolsbee["category"], "Central bank")
        self.assertEqual(goolsbee["importance"], "Low")
        self.assertIsNone(goolsbee["actual"])
        richmond = items[1]
        self.assertEqual(richmond["date"], "2026-09-22")
        self.assertEqual(richmond["time"], "9:00 AM CT")
        self.assertEqual(richmond["consensus"], "2")
        self.assertEqual(richmond["previous"], "4")
        compact = data_providers._parse_fair_economy_datetime("2026-09-22T08:30:00-0400")
        self.assertEqual(compact.utcoffset(), datetime.timedelta(hours=-4))

    def test_event_classification(self):
        cases = {
            "Fed Interest Rate Decision": "Central bank",
            "Nonfarm Payrolls": "Employment",
            "Initial Jobless Claims": "Employment",
            "GDP (QoQ)": "Growth",
            "ISM Manufacturing PMI": "Business surveys",
            "Retail Sales (MoM)": "Consumer",
            "10-Year Note Auction": "Treasury auction",
            "Something Obscure": "Economic data",
        }
        for title, category in cases.items():
            self.assertEqual(data_providers.classify_economic_event(title), category, title)

    def test_treasury_auctions_filter_to_window(self):
        records = [
            {"auction_date": "2026-09-22", "security_term": "2-Year", "security_type": "Note",
             "offering_amt": "69000000000", "cusip": "91282CAB1", "reopening": "No"},
            {"auction_date": "2026-09-30", "security_term": "7-Year", "security_type": "Note"},
        ]
        items = data_providers.parse_treasury_auctions(records, [datetime.date(2026, 9, 22), datetime.date(2026, 9, 23)])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "2-Year Note auction")
        self.assertIn("$69B", items[0]["detail"])
        self.assertIsNone(items[0]["time"])  # auction close time is not in the dataset

    def test_yahoo_earnings_marks_estimated_windows(self):
        days = [datetime.date(2026, 11, 18), datetime.date(2026, 11, 19)]
        estimated = data_providers.parse_yahoo_earnings(
            "NVDA", {"Earnings Date": [datetime.date(2026, 11, 18), datetime.date(2026, 11, 20)], "Earnings Average": 1.23}, days)
        self.assertEqual(estimated[0]["date_status"], "estimated_window")
        self.assertEqual(estimated[0]["consensus"], "EPS est. 1.23")
        listed = data_providers.parse_yahoo_earnings("AAPL", {"Earnings Date": [datetime.date(2026, 11, 19)]}, days)
        self.assertEqual(listed[0]["date_status"], "listed")
        self.assertEqual(data_providers.parse_yahoo_earnings("MSFT", {"Earnings Date": [datetime.date(2026, 12, 1)]}, days), [])

    def test_failed_provider_is_unavailable_not_fatal(self):
        with mock.patch.object(data_providers, "http_get", side_effect=OSError("blocked")):
            calendar = data_providers.build_market_calendar(
                datetime.date(2026, 9, 17),
                (),
                providers=(data_providers.fair_economy_economic_calendar, data_providers.market_structure_calendar),
            )
        statuses = {feed["id"]: feed["status"] for feed in calendar["feeds"]}
        self.assertEqual(statuses["fair_economy_economic"], "unavailable")
        self.assertEqual(statuses["market_structure"], "ok")
        self.assertEqual(calendar["window"], {
            "current_session": "2026-09-17", "next_session": "2026-09-18", "display_time_zone": "America/Chicago"})
        self.assertEqual([item["session"] for item in calendar["items"]], ["next"])
        self.assertNotIn("sort_key", calendar["items"][0])

    def test_disabled_feed_env(self):
        with mock.patch.dict(os.environ, {"DAILY_TAPE_DISABLED_FEEDS": "fair_economy_economic"}), \
                mock.patch.object(data_providers, "http_get") as get:
            feed = data_providers.fair_economy_economic_calendar([datetime.date(2026, 9, 22)])
        get.assert_not_called()
        self.assertEqual(feed["status"], "disabled")


class CatalystProviderTests(unittest.TestCase):
    start = datetime.datetime(2026, 9, 15, 16, 0, tzinfo=NY)
    end = datetime.datetime(2026, 9, 16, 17, 0, tzinfo=NY)

    def test_official_feed_keeps_only_timestamped_https_items_in_window(self):
        with mock.patch.object(data_providers, "http_get", return_value=RSS):
            feed = data_providers.official_catalysts(data_providers.OFFICIAL_FEEDS[0], self.start, self.end)
        self.assertEqual(feed["status"], "ok")
        self.assertEqual([item["title"] for item in feed["items"]], ["Federal Reserve issues FOMC statement"])
        item = feed["items"][0]
        self.assertEqual(item["publisher"], "Federal Reserve")
        self.assertEqual(item["category"], "Monetary policy")
        self.assertEqual(item["source_type"], "official")

    def test_news_publisher_allowlist_is_exact(self):
        stamp = ts(2026, 9, 16, 10)
        good = data_providers.normalize_news_item({
            "title": "Stocks rise", "link": "https://www.reuters.com/a", "publisher": "Reuters",
            "providerPublishTime": stamp, "relatedTickers": ["SPY"]})
        self.assertEqual(good["related_tickers"], ["SPY"])
        for publisher in ("Random Finance Blog", "SecuritiesDaily", "Motley Fool"):
            self.assertIsNone(data_providers.normalize_news_item({
                "title": "x", "link": "https://example.com", "publisher": publisher, "providerPublishTime": stamp}))
        self.assertIsNone(data_providers.normalize_news_item({
            "title": "No time", "link": "https://www.reuters.com/b", "publisher": "Reuters"}))

    def test_catalysts_prefer_official_sources_and_cap_count(self):
        def official(start, end):
            items = [{"title": f"Fed {i}", "url": f"https://fed/{i}", "publisher": "Federal Reserve",
                      "published_at": ts(2026, 9, 16, 9, i), "category": "Monetary policy",
                      "source_type": "official", "related_tickers": []} for i in range(5)]
            return data_providers.feed_result("fed", "Fed", "https://fed", items=items)

        def news(start, end):
            items = [{"title": f"News {i}", "url": f"https://news/{i}", "publisher": "Reuters",
                      "published_at": ts(2026, 9, 16, 12, i), "category": "Market news",
                      "source_type": "news", "related_tickers": []} for i in range(5)]
            return data_providers.feed_result("news", "News", "https://news", items=items)

        result = data_providers.build_verified_catalysts(self.start, self.end, max_items=6, providers=[official, news])
        kinds = [item["source_type"] for item in result["items"]]
        self.assertEqual(len(kinds), 6)
        self.assertEqual(kinds.count("official"), 3)
        self.assertEqual(result["items"], sorted(result["items"], key=lambda item: item["published_at"], reverse=True))
        self.assertTrue(all("items" not in feed for feed in result["feeds"]))

    def test_malformed_feed_is_unavailable(self):
        with mock.patch.object(data_providers, "http_get", return_value="<not-xml"):
            feed = data_providers.official_catalysts(data_providers.OFFICIAL_FEEDS[0], self.start, self.end)
        self.assertEqual(feed["status"], "unavailable")
        self.assertEqual(feed["items"], [])

    def test_fair_economy_http_payload_round_trip_and_deduplicates_weeks(self):
        payload = json.dumps([{
            "title": "Unemployment Claims",
            "country": "USD",
            "date": "2026-09-24T08:30:00-04:00",
            "impact": "Medium",
            "forecast": "201K",
            "previous": "196K",
        }])
        with mock.patch.object(data_providers, "http_get", return_value=payload) as get:
            feed = data_providers.fair_economy_economic_calendar([datetime.date(2026, 9, 24)])
        self.assertEqual(feed["status"], "ok")
        self.assertEqual(len(feed["items"]), 1)
        self.assertEqual(feed["items"][0]["category"], "Employment")
        self.assertEqual(feed["items"][0]["time"], "7:30 AM CT")
        self.assertEqual(feed["items"][0]["consensus"], "201K")
        self.assertEqual(get.call_count, 2)
        kwargs = get.call_args.kwargs
        self.assertEqual(kwargs["extra_headers"]["Referer"], data_providers.FOREX_FACTORY_CALENDAR_PAGE)
        self.assertIn("Mozilla/5.0", kwargs["extra_headers"]["User-Agent"])
        self.assertEqual(kwargs["attempts"], 2)

    def test_bls_aggregate_feed_falls_back_to_specific_release_feeds(self):
        bls = next(feed for feed in data_providers.OFFICIAL_FEEDS if feed["id"] == "bls_releases")
        fallback_rss = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
        <item><title>Consumer Price Index</title>
        <link>https://www.bls.gov/news.release/cpi.nr0.htm</link>
        <pubDate>Wed, 16 Sep 2026 18:00:00 GMT</pubDate></item>
        </channel></rss>"""
        calls = []

        def get(url, **kwargs):
            calls.append(url)
            if url == bls["url"]:
                raise OSError("aggregate blocked")
            return fallback_rss

        with mock.patch.object(data_providers, "http_get", side_effect=get):
            feed = data_providers.official_catalysts(bls, self.start, self.end)
        self.assertEqual(feed["status"], "ok")
        self.assertEqual([item["title"] for item in feed["items"]], ["Consumer Price Index"])
        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(any(url.endswith("/cpi.rss") for url in calls))

    def test_bls_403_stops_without_retrying_more_bls_paths(self):
        bls = next(feed for feed in data_providers.OFFICIAL_FEEDS if feed["id"] == "bls_releases")
        calls = []

        def get(url, **kwargs):
            calls.append(url)
            raise data_providers.urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

        with mock.patch.object(data_providers, "http_get", side_effect=get):
            feed = data_providers.official_catalysts(bls, self.start, self.end)
        self.assertEqual(feed["status"], "unavailable")
        self.assertEqual(feed["items"], [])
        self.assertEqual(len(calls), 1)
        self.assertIn("PermissionError", feed["error"])


class ContactEmailUserAgentTests(unittest.TestCase):
    def test_contact_email_is_sent_only_to_bls(self):
        with mock.patch.dict(os.environ, {"DAILY_TAPE_CONTACT_EMAIL": "tape@example.com"}):
            self.assertEqual(data_providers.user_agent_for("https://www.bls.gov/feed/bls_latest.rss"), "TheDailyTape/1.0 (tape@example.com)")
            self.assertEqual(data_providers.user_agent_for("https://www.federalreserve.gov/feeds/speeches.xml"), data_providers.USER_AGENT)

    def test_default_user_agent_without_contact_email(self):
        with mock.patch.dict(os.environ, {"DAILY_TAPE_CONTACT_EMAIL": ""}):
            self.assertEqual(data_providers.user_agent_for("https://www.bls.gov/feed/bls_latest.rss"), data_providers.USER_AGENT)


if __name__ == "__main__":
    unittest.main()
