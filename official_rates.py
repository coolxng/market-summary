"""Official U.S. rates and credit-spread series.

- U.S. Treasury daily par yield curve and real yield curve (official XML feed with CSV fallback).
- ICE BofA option-adjusted spreads published on FRED (no API key needed for
  the public fredgraph CSV endpoint).

Both publish once per business day with a lag: Treasury posts the curve late
in the afternoon and FRED's ICE series trail by a day. Every result carries
its own `as_of` date so pages can label stale values instead of implying they
belong to the report session.
"""

import csv
import datetime
import io
import re
import urllib.parse
import xml.etree.ElementTree as ET

from data_providers import clean_value, disabled_feeds, feed_result, http_get

TREASURY_XML_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
TREASURY_CSV_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all"
TREASURY_PAGE = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve"
TREASURY_REAL_PAGE = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_real_yield_curve"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

CURVE_TENORS = ("1m", "3m", "6m", "1y", "2y", "5y", "10y", "20y", "30y")
REAL_TENORS = ("5y", "10y", "30y")

CREDIT_SERIES = {
    "hy_oas": {"id": "BAMLH0A0HYM2", "name": "ICE BofA US High Yield OAS"},
    "ig_oas": {"id": "BAMLC0A0CM", "name": "ICE BofA US Corporate (IG) OAS"},
}


def tenor_key(header):
    """'2 Yr' -> '2y', '3 Mo' -> '3m', '1.5 Month' -> '1.5m', '10 YR' -> '10y'."""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(mo|mos|month|months|yr|yrs|year|years)\s*", header.strip(), re.I)
    if not match:
        return None
    unit = "m" if match.group(2).lower().startswith("mo") else "y"
    return f"{match.group(1)}{unit}"


def _parse_date(text):
    text = str(text or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _number(value):
    value = clean_value(value)
    if value is None or value == ".":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_treasury_csv(text):
    """Return [(date, {tenor: value})] sorted oldest first."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    rows = []
    for raw in reader:
        day = _parse_date(raw.get("Date"))
        if not day:
            continue
        values = {}
        for header, cell in raw.items():
            key = tenor_key(header or "")
            number = _number(cell)
            if key and number is not None:
                values[key] = number
        if values:
            rows.append((day, values))
    rows.sort(key=lambda item: item[0])
    return rows


def _xml_local_name(tag):
    return str(tag or "").rsplit("}", 1)[-1]


def _xml_tenor_key(field_name, prefix):
    if not field_name.startswith(prefix):
        return None
    raw = field_name[len(prefix):]
    match = re.fullmatch(r"(\d+)(MONTH|YEAR)", raw, re.I)
    if not match:
        return None
    unit = "m" if match.group(2).upper() == "MONTH" else "y"
    return f"{int(match.group(1))}{unit}"


def parse_treasury_xml(text, prefix="BC_"):
    """Parse Treasury's documented Atom/XML feed into dated tenor rows."""
    root = ET.fromstring(text)
    rows = []
    for properties in root.iter():
        if _xml_local_name(properties.tag) != "properties":
            continue
        day = None
        values = {}
        for child in properties:
            name = _xml_local_name(child.tag)
            if name == "NEW_DATE":
                day = _parse_date((child.text or "")[:10])
                continue
            key = _xml_tenor_key(name, prefix)
            value = _number(child.text)
            if key and value is not None:
                values[key] = value
        if day and values:
            rows.append((day, values))
    rows.sort(key=lambda item: item[0])
    return rows


def _treasury_rows(curve_type, anchor, fetch=http_get):
    """Use Treasury's documented XML feed first; retain CSV as a fallback."""
    rows = []
    prefix = "TC_" if curve_type == "daily_treasury_real_yield_curve" else "BC_"
    years = sorted({anchor.year - 1, anchor.year} if anchor.month == 1 else {anchor.year})
    for year in years:
        xml_query = urllib.parse.urlencode({"data": curve_type, "field_tdr_date_value": str(year)})
        try:
            xml_rows = parse_treasury_xml(
                fetch(f"{TREASURY_XML_URL}?{xml_query}", accept="application/xml, text/xml, */*"),
                prefix=prefix,
            )
            if not xml_rows:
                raise ValueError("Treasury XML returned no usable rows")
            rows.extend(xml_rows)
            continue
        except Exception as xml_exc:
            print(f"  Treasury XML {curve_type} fallback: {xml_exc.__class__.__name__}")

        csv_query = urllib.parse.urlencode({
            "type": curve_type,
            "field_tdr_date_value": str(year),
            "page": "",
            "_format": "csv",
        })
        rows.extend(parse_treasury_csv(
            fetch(f"{TREASURY_CSV_URL.format(year=year)}?{csv_query}", accept="text/csv")
        ))
    rows.sort(key=lambda item: item[0])
    return [row for row in rows if row[0] <= anchor]


def _change_bp(current, previous):
    if current is None or previous is None:
        return None
    return round((current - previous) * 100, 1)


def summarize_curve(rows, tenors):
    if not rows:
        return None
    (as_of, latest), previous = rows[-1], (rows[-2] if len(rows) > 1 else (None, {}))
    prior_date, prior = previous
    summary = {
        "as_of": as_of.isoformat(),
        "previous_date": prior_date.isoformat() if prior_date else None,
        "tenors": {
            tenor: {"value": latest[tenor], "change_bp": _change_bp(latest[tenor], prior.get(tenor))}
            for tenor in tenors if tenor in latest
        },
    }
    return summary


def _spread(latest, prior, long_tenor, short_tenor):
    if long_tenor not in latest or short_tenor not in latest:
        return None
    value = round((latest[long_tenor] - latest[short_tenor]) * 100, 1)
    previous = None
    if long_tenor in prior and short_tenor in prior:
        previous = round((prior[long_tenor] - prior[short_tenor]) * 100, 1)
    return {"value_bp": value, "change_bp": None if previous is None else round(value - previous, 1)}


def fetch_treasury_rates(anchor, fetch=http_get):
    """Latest official nominal curve, key spreads and real yields on or before `anchor`."""
    if "treasury_curve" in disabled_feeds():
        return {**feed_result("treasury_curve", "U.S. Treasury daily par yield curve", TREASURY_PAGE, status="disabled"), "curve": None, "spreads": {}, "real": None}
    try:
        nominal_rows = _treasury_rows("daily_treasury_yield_curve", anchor, fetch)
        curve = summarize_curve(nominal_rows, CURVE_TENORS)
        if curve is None:
            raise ValueError("no curve rows on or before anchor")
    except Exception as exc:
        print(f"  Treasury yield curve unavailable: {exc.__class__.__name__}")
        return {
            **feed_result("treasury_curve", "U.S. Treasury daily par yield curve", TREASURY_PAGE,
                          error=f"Treasury yield curve unavailable ({exc.__class__.__name__})."),
            "curve": None, "spreads": {}, "real": None,
        }
    latest = nominal_rows[-1][1]
    prior = nominal_rows[-2][1] if len(nominal_rows) > 1 else {}
    real = None
    try:
        real = summarize_curve(_treasury_rows("daily_treasury_real_yield_curve", anchor, fetch), REAL_TENORS)
    except Exception as exc:
        print(f"  Treasury real yield curve unavailable: {exc.__class__.__name__}")
    return {
        **feed_result("treasury_curve", "U.S. Treasury daily par yield curve", TREASURY_PAGE, status="ok"),
        "curve": curve,
        "spreads": {
            "2s10s": _spread(latest, prior, "10y", "2y"),
            "3m10y": _spread(latest, prior, "10y", "3m"),
            "5s30s": _spread(latest, prior, "30y", "5y"),
        },
        "real": real,
        "real_source_url": TREASURY_REAL_PAGE,
    }


def parse_fred_csv(text):
    """FRED CSV: first column is the date (DATE or observation_date); '.' marks missing."""
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")))
    header = next(reader, None)
    if not header or len(header) < 2:
        raise ValueError("unexpected FRED header")
    rows = []
    for raw in reader:
        if len(raw) < 2:
            continue
        day = _parse_date(raw[0])
        value = _number(raw[1])
        if day and value is not None:
            rows.append((day, value))
    rows.sort(key=lambda item: item[0])
    return rows


def fetch_credit_spreads(anchor, fetch=http_get):
    """ICE BofA option-adjusted spreads (percentage points) from FRED, as basis points."""
    series = {}
    if "fred_credit" in disabled_feeds():
        return {**feed_result("fred_credit", "FRED credit spreads", "https://fred.stlouisfed.org/", status="disabled"), "series": series}
    errors = 0
    for key, meta in CREDIT_SERIES.items():
        start = (anchor - datetime.timedelta(days=21)).isoformat()
        url = f"{FRED_CSV_URL}?{urllib.parse.urlencode({'id': meta['id'], 'cosd': start, 'coed': anchor.isoformat()})}"
        try:
            rows = [row for row in parse_fred_csv(fetch(url, accept="text/csv")) if row[0] <= anchor]
            if not rows:
                raise ValueError("no observations")
            (as_of, value), prior = rows[-1], (rows[-2] if len(rows) > 1 else None)
            series[key] = {
                "name": meta["name"],
                "series_id": meta["id"],
                "value_bp": round(value * 100, 0),
                "change_bp": round((value - prior[1]) * 100, 0) if prior else None,
                "as_of": as_of.isoformat(),
                "source_url": f"https://fred.stlouisfed.org/series/{meta['id']}",
            }
        except Exception as exc:
            errors += 1
            print(f"  FRED {meta['id']} unavailable: {exc.__class__.__name__}")
    error = "One or more FRED credit spread series were unavailable." if errors else None
    status = "unavailable" if errors == len(CREDIT_SERIES) else "ok"
    return {**feed_result("fred_credit", "FRED credit spreads (ICE BofA OAS)", "https://fred.stlouisfed.org/", status=status, error=error), "series": series}
