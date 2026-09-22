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


if __name__ == "__main__":
    unittest.main()
