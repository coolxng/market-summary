import json
import os
import sys
import types
import unittest
from unittest import mock

sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=None))

import delivery  # noqa: E402
import morning_cron  # noqa: E402
import railway_cron  # noqa: E402

SNAPSHOT = {
    "session_date": "2026-09-21",
    "market_data": {"^GSPC": {"pct_change": 1.49, "end_price": 6764.7}},
    "daily_market_breadth": {"advances": 7},
    "daily_sector_performance": {f"S{i}": 0.1 for i in range(11)},
    "derived_metrics": {"risk_confirmation": {"signal": "risk_on_confirmed"}},
    "data_quality": {"overall": "partial"},
    "narrative": {"editorial": {"headline": "Breadth confirms the rally"}},
}


class RecordingChannel:
    name = "recording"

    def __init__(self):
        self.sent = []

    def configured(self):
        return True

    def send(self, publication):
        self.sent.append(publication)
        return True


class DeliveryTests(unittest.TestCase):
    def test_close_publication_fields(self):
        publication = delivery.close_publication(SNAPSHOT, "https://example.test/market-summary/")
        fields = dict(publication.fields)
        self.assertEqual(publication.title, "📈 Breadth confirms the rally")
        self.assertEqual(fields["Session"], "Monday, September 21, 2026")
        self.assertEqual(fields["S&P 500"], "+1.49% to 6,764.70")
        self.assertEqual(fields["Breadth"], "7 of 11 sectors up")
        self.assertEqual(fields["Regime"], "Constructive")
        self.assertEqual(fields["Data status"], "Partial")
        self.assertIn("https://example.test/market-summary/reports/2026-09-21/", fields["Archive"])

    def test_missing_values_are_labeled_not_zero(self):
        fields = dict(delivery.close_publication({"session_date": "2026-09-21"}, "https://x.test/").fields)
        self.assertEqual(fields["S&P 500"], "Unavailable")
        self.assertEqual(fields["Breadth"], "Unavailable")
        self.assertEqual(fields["Regime"], "Unavailable")

    def test_discord_payload_disables_mentions_and_truncates(self):
        channel = delivery.DiscordWebhookChannel("https://discord.invalid/hook")
        payload = channel.payload(delivery.Publication(kind="close", title="x" * 400, url="https://x", summary="y", fields=(("a", ""),)))
        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        self.assertEqual(len(payload["embeds"][0]["title"]), 256)
        self.assertEqual(payload["embeds"][0]["fields"][0]["value"], "—")

    def test_failure_text_redacts_secrets(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_supersecretvalue"}):
            publication = delivery.failure_publication(RuntimeError("bad token ghp_supersecretvalue"), "https://x/")
        self.assertNotIn("ghp_supersecretvalue", publication.summary)
        self.assertIn("[GITHUB_TOKEN redacted]", publication.summary)

    def test_unconfigured_discord_does_not_send(self):
        with mock.patch.object(delivery.urllib.request, "urlopen") as urlopen:
            self.assertFalse(delivery.DiscordWebhookChannel("").send(delivery.Publication("close", "t", "u", "s")))
        urlopen.assert_not_called()

    def test_send_posts_json_without_leaking_url_on_failure(self):
        channel = delivery.DiscordWebhookChannel("https://discord.invalid/secret-hook")
        with mock.patch.object(delivery.urllib.request, "urlopen", side_effect=OSError("https://discord.invalid/secret-hook down")), \
                mock.patch("sys.stderr") as stderr:
            self.assertFalse(channel.send(delivery.Publication("close", "t", "u", "s")))
        written = "".join(call.args[0] for call in stderr.write.call_args_list)
        self.assertNotIn("secret-hook", written)


class NoSpamTests(unittest.TestCase):
    def test_close_cron_is_silent_without_a_new_session(self):
        channel = RecordingChannel()
        with mock.patch.object(railway_cron, "deliver", side_effect=lambda publication: delivery.deliver(publication, [channel])):
            railway_cron.send_success_notification(SNAPSHOT, {"updated": False, "commit_sha": None})
            self.assertEqual(channel.sent, [])
            railway_cron.send_success_notification(SNAPSHOT, {"updated": True, "commit_sha": "abc1234"})
        self.assertEqual([publication.kind for publication in channel.sent], ["close"])

    def test_morning_cron_is_silent_without_a_commit(self):
        channel = RecordingChannel()
        snapshot = {"market_date": "2026-09-22", "futures": {"ES=F": {"pct_change": 0.4}}, "data_quality": {"coverage_pct": 94}, "status": "ready",
                    "what_matters_today": [{"label": "Futures", "text": "S&P 500 E-mini futures +0.40%."}]}
        with mock.patch.object(morning_cron, "deliver", side_effect=lambda publication: delivery.deliver(publication, [channel])):
            morning_cron.notify(snapshot, None)
            self.assertEqual(channel.sent, [])
            morning_cron.notify(snapshot, "abc")
        self.assertEqual(channel.sent[0].kind, "morning")
        self.assertIn("S&P 500 E-mini futures +0.40%.", channel.sent[0].summary)
        self.assertEqual(json.loads(json.dumps(dict(channel.sent[0].fields)))["S&P futures"], "+0.40%")


if __name__ == "__main__":
    unittest.main()
