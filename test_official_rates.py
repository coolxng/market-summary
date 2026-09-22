import datetime
import unittest

import official_rates

NOMINAL = '''Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"
09/21/2026,4.20,4.19,4.18,4.10,4.05,3.95,3.80,3.55,3.50,3.60,3.75,3.95,4.40,4.55
09/18/2026,4.21,4.20,4.19,4.12,4.06,3.97,3.83,3.60,3.54,3.63,3.77,3.96,4.41,4.57
'''
REAL = '''Date,"5 YR","7 YR","10 YR","20 YR","30 YR"
09/21/2026,1.20,1.35,1.55,1.85,2.00
09/18/2026,1.22,1.36,1.56,1.86,2.02
'''

NOMINAL_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
  <entry><content type="application/xml"><m:properties>
    <d:NEW_DATE m:type="Edm.DateTime">2026-09-18T00:00:00</d:NEW_DATE>
    <d:BC_3MONTH m:type="Edm.Double">4.12</d:BC_3MONTH>
    <d:BC_2YEAR m:type="Edm.Double">3.60</d:BC_2YEAR>
    <d:BC_10YEAR m:type="Edm.Double">3.96</d:BC_10YEAR>
    <d:BC_30YEAR m:type="Edm.Double">4.57</d:BC_30YEAR>
  </m:properties></content></entry>
  <entry><content type="application/xml"><m:properties>
    <d:NEW_DATE m:type="Edm.DateTime">2026-09-21T00:00:00</d:NEW_DATE>
    <d:BC_3MONTH m:type="Edm.Double">4.10</d:BC_3MONTH>
    <d:BC_2YEAR m:type="Edm.Double">3.55</d:BC_2YEAR>
    <d:BC_10YEAR m:type="Edm.Double">3.95</d:BC_10YEAR>
    <d:BC_30YEAR m:type="Edm.Double">4.55</d:BC_30YEAR>
  </m:properties></content></entry>
</feed>"""


def fake_fetch(url, accept=None):
    if "real_yield" in url:
        return REAL
    return NOMINAL


class TreasuryCurveTests(unittest.TestCase):
    def test_xml_feed_parser(self):
        rows = official_rates.parse_treasury_xml(NOMINAL_XML, prefix="BC_")
        self.assertEqual(rows[-1][0], datetime.date(2026, 9, 21))
        self.assertEqual(rows[-1][1]["2y"], 3.55)
        self.assertEqual(rows[-1][1]["10y"], 3.95)

    def test_xml_is_primary_and_csv_is_fallback(self):
        calls = []

        def fetch(url, accept=None):
            calls.append(url)
            if "pages/xml" in url:
                return NOMINAL_XML
            raise AssertionError("CSV fallback should not be needed")

        rates = official_rates.fetch_treasury_rates(datetime.date(2026, 9, 22), fetch=fetch)
        self.assertEqual(rates["status"], "ok")
        self.assertEqual(rates["curve"]["as_of"], "2026-09-21")
        self.assertTrue(all("pages/xml" in url for url in calls))

    def test_tenor_headers(self):
        self.assertEqual(official_rates.tenor_key("2 Yr"), "2y")
        self.assertEqual(official_rates.tenor_key("3 Mo"), "3m")
        self.assertEqual(official_rates.tenor_key("1.5 Month"), "1.5m")
        self.assertEqual(official_rates.tenor_key("10 YR"), "10y")
        self.assertIsNone(official_rates.tenor_key("Date"))

    def test_curve_spreads_and_real_yields(self):
        rates = official_rates.fetch_treasury_rates(datetime.date(2026, 9, 22), fetch=fake_fetch)
        self.assertEqual(rates["status"], "ok")
        curve = rates["curve"]
        self.assertEqual(curve["as_of"], "2026-09-21")
        self.assertEqual(curve["previous_date"], "2026-09-18")
        self.assertEqual(curve["tenors"]["2y"], {"value": 3.55, "change_bp": -5.0})
        self.assertEqual(rates["spreads"]["2s10s"], {"value_bp": 40.0, "change_bp": 4.0})
        self.assertEqual(rates["spreads"]["3m10y"]["value_bp"], -15.0)
        self.assertEqual(rates["real"]["tenors"]["10y"], {"value": 1.55, "change_bp": -1.0})

    def test_anchor_excludes_later_rows(self):
        rates = official_rates.fetch_treasury_rates(datetime.date(2026, 9, 18), fetch=fake_fetch)
        self.assertEqual(rates["curve"]["as_of"], "2026-09-18")
        self.assertIsNone(rates["curve"]["tenors"]["2y"]["change_bp"])  # no prior row, no invented change

    def test_failure_is_unavailable(self):
        def broken(url, accept=None):
            raise OSError("blocked")
        rates = official_rates.fetch_treasury_rates(datetime.date(2026, 9, 22), fetch=broken)
        self.assertEqual(rates["status"], "unavailable")
        self.assertIsNone(rates["curve"])
        self.assertEqual(rates["spreads"], {})


class FredTests(unittest.TestCase):
    def test_parse_handles_both_headers_and_missing_values(self):
        for header in ("DATE", "observation_date"):
            rows = official_rates.parse_fred_csv(f"{header},BAMLH0A0HYM2\n2026-09-17,3.10\n2026-09-18,.\n2026-09-21,3.05\n")
            self.assertEqual(rows, [(datetime.date(2026, 9, 17), 3.10), (datetime.date(2026, 9, 21), 3.05)])

    def test_credit_spreads_in_basis_points(self):
        def fetch(url, accept=None):
            return "observation_date,X\n2026-09-17,3.10\n2026-09-18,3.05\n"
        result = official_rates.fetch_credit_spreads(datetime.date(2026, 9, 21), fetch=fetch)
        self.assertEqual(result["status"], "ok")
        hy = result["series"]["hy_oas"]
        self.assertEqual((hy["value_bp"], hy["change_bp"], hy["as_of"]), (305.0, -5.0, "2026-09-18"))

    def test_credit_spreads_unavailable(self):
        def fetch(url, accept=None):
            raise OSError("blocked")
        result = official_rates.fetch_credit_spreads(datetime.date(2026, 9, 21), fetch=fetch)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["series"], {})


if __name__ == "__main__":
    unittest.main()
