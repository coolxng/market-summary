import datetime
import os
import unittest
from unittest import mock

import sys
import types

sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=None))

import morning_cron  # noqa: E402


class MorningScheduleTests(unittest.TestCase):
    def test_daylight_saving_slot_runs_at_745_central(self):
        now = datetime.datetime(2026, 9, 21, 12, 45, tzinfo=datetime.timezone.utc)
        self.assertTrue(morning_cron.should_publish_now(now))

    def test_daylight_saving_second_slot_is_skipped(self):
        now = datetime.datetime(2026, 9, 21, 13, 45, tzinfo=datetime.timezone.utc)
        self.assertFalse(morning_cron.should_publish_now(now))

    def test_standard_time_slot_runs_at_745_central(self):
        now = datetime.datetime(2026, 12, 7, 13, 45, tzinfo=datetime.timezone.utc)
        self.assertTrue(morning_cron.should_publish_now(now))

    def test_standard_time_early_slot_is_skipped(self):
        now = datetime.datetime(2026, 12, 7, 12, 45, tzinfo=datetime.timezone.utc)
        self.assertFalse(morning_cron.should_publish_now(now))

    def test_weekend_is_skipped(self):
        now = datetime.datetime(2026, 9, 20, 12, 45, tzinfo=datetime.timezone.utc)
        self.assertFalse(morning_cron.should_publish_now(now))

    def test_force_override_supports_manual_runs(self):
        now = datetime.datetime(2026, 9, 20, 2, 0, tzinfo=datetime.timezone.utc)
        with mock.patch.dict(os.environ, {"MORNING_TAPE_FORCE": "1"}):
            self.assertTrue(morning_cron.should_publish_now(now))


if __name__ == "__main__":
    unittest.main()
