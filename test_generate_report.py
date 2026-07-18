import datetime
import sys
import types
import unittest

sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=None))

import generate_report


class GenerateReportTests(unittest.TestCase):
    def test_compute_week_window_anchors_to_previous_friday(self):
        now = datetime.datetime(2026, 6, 17, 12, 0, tzinfo=generate_report.NY_TZ)
        start_date, end_date = generate_report.compute_week_window(now)
        self.assertEqual(start_date.isoformat(), "2026-06-05")
        self.assertEqual(end_date.isoformat(), "2026-06-12")

    def test_render_html_with_strong_escapes_other_markup(self):
        raw = '<script>alert(1)</script><strong>Leader</strong>'
        sanitized = generate_report.render_html_with_strong(raw)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", sanitized)
        self.assertIn("<strong>Leader</strong>", sanitized)

    def test_preserve_premium_shell_replaces_body_and_title(self):
        legacy = "<title>Old</title><style>body { color: black; }</style><body>old</body>"
        self.assertIsNone(generate_report.preserve_premium_shell(legacy, "New", "<main>new</main>"))

        premium = legacy.replace(
            "<style>",
            f"<style>/* {generate_report.PREMIUM_DESIGN_MARKER} */",
        )
        rendered = generate_report.preserve_premium_shell(
            premium,
            "New & Safe",
            "<main>new</main>",
        )
        self.assertIn("<title>New &amp; Safe</title>", rendered)
        self.assertIn("<main>new</main>", rendered)
        self.assertNotIn("<body>old</body>", rendered)

    def test_nikkei_sanity_bound_accepts_current_index_levels(self):
        self.assertTrue(generate_report.is_sane("^N225", 64141.12))

    def test_validate_dataset_rejects_zeroed_core_data(self):
        with self.assertRaisesRegex(ValueError, "end price is invalid"):
            generate_report.validate_dataset(
                {"end_price": 0.0, "closes": [0.0], "ticker_used": "^GSPC", "error": None},
                "^GSPC",
            )

    def test_validate_core_datasets_accepts_valid_core_set(self):
        valid = {
            ticker: {"end_price": 100.0, "closes": [95.0, 100.0], "ticker_used": ticker, "error": None}
            for ticker in generate_report.CORE_TICKERS
        }
        valid["^GSPC"]["end_price"] = 6000.0
        valid["^IXIC"]["end_price"] = 19000.0
        valid["^DJI"]["end_price"] = 42000.0
        valid["^RUT"]["end_price"] = 2100.0
        valid["^VIX"]["end_price"] = 20.0
        valid["^TNX"]["end_price"] = 4.2
        valid["DX-Y.NYB"]["end_price"] = 102.0
        generate_report.validate_core_datasets(valid)


if __name__ == "__main__":
    unittest.main()
