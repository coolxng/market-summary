import datetime
import os
import unittest
from unittest import mock

import railway_cron


class CloseScheduleTests(unittest.TestCase):
    def test_daylight_saving_slot_runs_at_330_central(self):
        now = datetime.datetime(2026, 9, 21, 20, 30, tzinfo=datetime.timezone.utc)
        self.assertTrue(railway_cron.should_publish_now(now))

    def test_daylight_saving_second_slot_is_skipped(self):
        now = datetime.datetime(2026, 9, 21, 21, 30, tzinfo=datetime.timezone.utc)
        self.assertFalse(railway_cron.should_publish_now(now))

    def test_standard_time_slot_runs_at_330_central(self):
        now = datetime.datetime(2026, 12, 7, 21, 30, tzinfo=datetime.timezone.utc)
        self.assertTrue(railway_cron.should_publish_now(now))

    def test_standard_time_early_slot_is_skipped(self):
        now = datetime.datetime(2026, 12, 7, 20, 30, tzinfo=datetime.timezone.utc)
        self.assertFalse(railway_cron.should_publish_now(now))

    def test_force_override_supports_manual_runs(self):
        now = datetime.datetime(2026, 9, 20, 2, 0, tzinfo=datetime.timezone.utc)
        with mock.patch.dict(os.environ, {"MARKET_SUMMARY_FORCE": "1"}):
            self.assertTrue(railway_cron.should_publish_now(now))


if __name__ == "__main__":
    unittest.main()
