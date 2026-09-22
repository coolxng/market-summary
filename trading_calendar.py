"""Rule-based U.S. equity market calendar.

These rules reproduce the published NYSE holiday and early-close schedule and the
standard monthly options expiration convention (third Friday, moved to Thursday
when that Friday is an exchange holiday). They cannot anticipate unscheduled
closures such as national days of mourning, so every rule-derived calendar item
is labeled as rule-based in the report.
"""

import datetime

NYSE_HOURS_URL = "https://www.nyse.com/markets/hours-calendars"
OCC_EXPIRATION_URL = "https://www.theocc.com/"


def _nth_weekday(year, month, weekday, occurrence):
    first = datetime.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + datetime.timedelta(days=offset + (occurrence - 1) * 7)


def _last_weekday(year, month, weekday):
    if month == 12:
        last = datetime.date(year, 12, 31)
    else:
        last = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    return last - datetime.timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day):
    if day.weekday() == 5:
        return day - datetime.timedelta(days=1)
    if day.weekday() == 6:
        return day + datetime.timedelta(days=1)
    return day


def easter_sunday(year):
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return datetime.date(year, month, day)


def nyse_holidays(year):
    """Return {date: name} for full-day NYSE closures in `year`."""
    holidays = {}
    new_year = datetime.date(year, 1, 1)
    # NYSE does not observe New Year's Day on the preceding Friday.
    if new_year.weekday() != 5:
        holidays[_observed(new_year)] = "New Year's Day"
    holidays[_nth_weekday(year, 1, 0, 3)] = "Martin Luther King Jr. Day"
    holidays[_nth_weekday(year, 2, 0, 3)] = "Washington's Birthday"
    holidays[easter_sunday(year) - datetime.timedelta(days=2)] = "Good Friday"
    holidays[_last_weekday(year, 5, 0)] = "Memorial Day"
    if year >= 2022:
        holidays[_observed(datetime.date(year, 6, 19))] = "Juneteenth"
    holidays[_observed(datetime.date(year, 7, 4))] = "Independence Day"
    holidays[_nth_weekday(year, 9, 0, 1)] = "Labor Day"
    holidays[_nth_weekday(year, 11, 3, 4)] = "Thanksgiving Day"
    holidays[_observed(datetime.date(year, 12, 25))] = "Christmas Day"
    # A Saturday New Year's Day in the following year is not observed on Dec 31.
    return holidays


def _holiday_name(day):
    return nyse_holidays(day.year).get(day)


def is_trading_day(day):
    return day.weekday() < 5 and _holiday_name(day) is None


def next_trading_day(day):
    candidate = day + datetime.timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += datetime.timedelta(days=1)
    return candidate


def previous_trading_day(day):
    candidate = day - datetime.timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= datetime.timedelta(days=1)
    return candidate


def early_close_reason(day):
    """NYSE closes at 1:00 PM ET on these sessions when they are trading days."""
    if not is_trading_day(day):
        return None
    if day == _nth_weekday(day.year, 11, 3, 4) + datetime.timedelta(days=1):
        return "Day after Thanksgiving"
    if day.month == 12 and day.day == 24:
        return "Christmas Eve"
    if day.month == 7 and day.day == 3:
        return "Independence Day eve"
    return None


def monthly_options_expiration(year, month):
    third_friday = _nth_weekday(year, month, 4, 3)
    if is_trading_day(third_friday):
        return third_friday
    return previous_trading_day(third_friday)


def session_window(anchor):
    """Current trading session (if `anchor` trades) plus the next trading session."""
    days = []
    if is_trading_day(anchor):
        days.append(anchor)
    days.append(next_trading_day(anchor))
    return days


def closures_between(start, end):
    """Weekday exchange holidays strictly between two dates."""
    closures = []
    day = start + datetime.timedelta(days=1)
    while day < end:
        name = _holiday_name(day)
        if name and day.weekday() < 5:
            closures.append((day, name))
        day += datetime.timedelta(days=1)
    return closures


def market_structure_events(days):
    """Rule-derived holidays, early closes and options expirations for `days`."""
    events = []
    if len(days) >= 2:
        for day, name in closures_between(days[0], days[-1]):
            events.append({
                "date": day.isoformat(),
                "time": None,
                "time_status": "all_day",
                "title": f"U.S. equity markets closed ({name})",
                "category": "Market structure",
                "kind": "market_structure",
                "source": "NYSE holiday rules",
                "source_url": NYSE_HOURS_URL,
                "rule_based": True,
            })
    for day in days:
        reason = early_close_reason(day)
        if reason:
            events.append({
                "date": day.isoformat(),
                "time": "12:00 PM CT",
                "time_status": "scheduled",
                "title": f"Early close: U.S. equities close at 1:00 PM ET ({reason})",
                "category": "Market structure",
                "kind": "market_structure",
                "source": "NYSE holiday and early-close rules",
                "source_url": NYSE_HOURS_URL,
                "rule_based": True,
            })
        if day == monthly_options_expiration(day.year, day.month):
            quarterly = day.month in (3, 6, 9, 12)
            events.append({
                "date": day.isoformat(),
                "time": None,
                "time_status": "all_day",
                "title": "Quarterly options and index futures expiration" if quarterly else "Monthly equity options expiration",
                "category": "Market structure",
                "kind": "market_structure",
                "source": "Standard third-Friday expiration convention",
                "source_url": OCC_EXPIRATION_URL,
                "rule_based": True,
            })
    return events
