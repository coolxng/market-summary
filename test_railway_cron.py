import datetime
import os
import unittest
from unittest import mock

import railway_cron


class CloseScheduleTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = mock.patch.dict(
            os.environ,
            {
                "MARKET_SUMMARY_FORCE": "",
                "MARKET_SUMMARY_REGENERATE": "",
                "MARKET_SUMMARY_PAUSED": "",
            },
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_daylight_saving_primary_slot_runs_at_330_central(self):
        now = datetime.datetime(2026, 9, 21, 20, 30, tzinfo=datetime.timezone.utc)
        self.assertTrue(railway_cron.should_publish_now(now))

    def test_daylight_saving_retry_slots_run_through_415_central(self):
        for now in (
            datetime.datetime(2026, 9, 21, 20, 45, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 9, 21, 21, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 9, 21, 21, 15, tzinfo=datetime.timezone.utc),
        ):
            with self.subTest(now=now):
                self.assertTrue(railway_cron.should_publish_now(now))

    def test_daylight_saving_430_slot_is_skipped(self):
        now = datetime.datetime(2026, 9, 21, 21, 30, tzinfo=datetime.timezone.utc)
        self.assertFalse(railway_cron.should_publish_now(now))

    def test_standard_time_primary_slot_runs_at_330_central(self):
        now = datetime.datetime(2026, 12, 7, 21, 30, tzinfo=datetime.timezone.utc)
        self.assertTrue(railway_cron.should_publish_now(now))

    def test_standard_time_retry_slots_run_through_415_central(self):
        for now in (
            datetime.datetime(2026, 12, 7, 21, 45, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 12, 7, 22, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2026, 12, 7, 22, 15, tzinfo=datetime.timezone.utc),
        ):
            with self.subTest(now=now):
                self.assertTrue(railway_cron.should_publish_now(now))

    def test_standard_time_230_slot_is_skipped(self):
        now = datetime.datetime(2026, 12, 7, 20, 30, tzinfo=datetime.timezone.utc)
        self.assertFalse(railway_cron.should_publish_now(now))

    def test_force_override_supports_manual_runs(self):
        now = datetime.datetime(2026, 9, 20, 2, 0, tzinfo=datetime.timezone.utc)
        with mock.patch.dict(os.environ, {"MARKET_SUMMARY_FORCE": "1"}):
            self.assertTrue(railway_cron.should_publish_now(now))

    def test_preflight_skips_when_today_is_already_published(self):
        now = datetime.datetime(2026, 9, 21, 20, 45, tzinfo=datetime.timezone.utc)
        with mock.patch.object(
            railway_cron,
            "remote_snapshot",
            return_value={"session_date": "2026-09-21"},
        ):
            self.assertTrue(railway_cron.already_published_for_local_date(now))

    def test_preflight_retries_when_remote_session_is_stale(self):
        now = datetime.datetime(2026, 9, 21, 20, 45, tzinfo=datetime.timezone.utc)
        with mock.patch.object(
            railway_cron,
            "remote_snapshot",
            return_value={"session_date": "2026-09-18"},
        ):
            self.assertFalse(railway_cron.already_published_for_local_date(now))

    def test_regeneration_bypasses_preflight(self):
        now = datetime.datetime(2026, 9, 21, 20, 45, tzinfo=datetime.timezone.utc)
        with mock.patch.dict(os.environ, {"MARKET_SUMMARY_REGENERATE": "1"}):
            with mock.patch.object(railway_cron, "remote_snapshot") as remote_snapshot:
                self.assertFalse(railway_cron.already_published_for_local_date(now))
                remote_snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
