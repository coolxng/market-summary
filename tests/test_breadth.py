import unittest

import breadth


def hist(closes, dividends=None, start=1):
    dates = [f"2026-09-{day:02d}" for day in range(start, start + len(closes))]
    return {"dates": dates, "closes": closes, "dividends": dividends or {}}


class BreadthTests(unittest.TestCase):
    def test_total_return_counts_dividends(self):
        # Price drops 0.50 on the ex-date but a 0.60 dividend was paid: a gain, not a decline.
        returns = breadth.daily_total_returns(hist([100.0, 99.5], {"2026-09-02": 0.6}))
        self.assertEqual(returns, {"2026-09-02": 0.1})

    def test_ad_line_requires_full_universe_and_window(self):
        up = hist([100 + i for i in range(22)])
        down = hist([100 - i * 0.5 for i in range(22)])
        line = breadth.sector_ad_line([up] * 7 + [down] * 4, sessions=20)
        self.assertEqual(len(line["dates"]), 20)
        self.assertEqual(line["net_advancing"][0], 3)
        self.assertEqual(line["cumulative"][-1], 60)
        self.assertIsNone(breadth.sector_ad_line([up] * 10, sessions=20))
        self.assertIsNone(breadth.sector_ad_line([up] * 11, sessions=30))

    def test_ad_line_uses_only_shared_dates(self):
        early = hist([100 + i for i in range(22)], start=1)
        late = hist([100 + i for i in range(22)], start=3)
        line = breadth.sector_ad_line([early] * 6 + [late] * 5, sessions=5)
        self.assertEqual(line["dates"][-1], "2026-09-22")
        self.assertEqual(line["dates"][0], "2026-09-18")

    def test_relative_return_in_percentage_points(self):
        rsp = hist([100.0, 101.0, 102.01])
        spy = hist([100.0, 100.0, 100.0])
        self.assertEqual(breadth.relative_return(rsp, spy, 2), 2.01)
        self.assertIsNone(breadth.relative_return(rsp, spy, 5))

    def test_regime_rule_matches_published_thresholds(self):
        self.assertEqual(breadth.classify_regime(0.5, -2.0, [1.0] * 7 + [-1.0] * 4), "risk_on_confirmed")
        self.assertEqual(breadth.classify_regime(0.5, -2.0, [1.0] * 6 + [-1.0] * 5), "mixed")  # 54.5% < 60%
        self.assertEqual(breadth.classify_regime(0.5, -2.0, [1.0] * 10), "mixed")  # incomplete coverage
        self.assertEqual(breadth.classify_regime(-0.5, 3.0, [1.0] * 4 + [-1.0] * 7), "risk_off_confirmed")
        self.assertEqual(breadth.classify_regime(None, 3.0, [1.0] * 11), "unavailable")

    def test_regime_history_uses_same_day_moves_only(self):
        sp = hist([100.0, 101.0, 100.0, 100.5])
        vix = hist([20.0, 19.0, 21.0])  # no VIX bar for the last day
        up = hist([10.0, 10.1, 10.0, 10.2])
        history = breadth.regime_history(sp, vix, [up] * 11, sessions=60)
        self.assertEqual([row["signal"] for row in history], ["risk_on_confirmed", "risk_off_confirmed", "unavailable"])
        self.assertEqual(history[0]["sectors_positive"], 11)
        self.assertEqual(history[-1]["vix_pct"], None)
        self.assertTrue(all(row["basis"] == "reconstructed" for row in history))


if __name__ == "__main__":
    unittest.main()
