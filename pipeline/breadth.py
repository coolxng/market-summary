"""Breadth and participation measures built from stored daily history.

Every measure here uses a transparent tracked universe (the 11 S&P sector
ETFs, SPY/RSP). None of them is labeled or presented as exchange-wide
NYSE/Nasdaq breadth.

Daily returns are total returns: (close + dividend) / previous close - 1.
That matches how the report's own daily moves are measured (dividend-
adjusted Yahoo closes), so an ex-dividend date does not register as a
decline.
"""


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and value not in (float("inf"), float("-inf"))


def daily_total_returns(history):
    """{date: pct_change rounded to 2dp} for each session after the first."""
    dates = history.get("dates") or []
    closes = history.get("closes") or []
    dividends = history.get("dividends") or {}
    returns = {}
    for index in range(1, min(len(dates), len(closes))):
        previous, current = closes[index - 1], closes[index]
        if not _finite(previous) or not _finite(current) or previous <= 0:
            continue
        dividend = dividends.get(dates[index], 0.0) or 0.0
        returns[dates[index]] = round(((current + dividend) / previous - 1) * 100, 2)
    return returns


def _common_dates(return_maps):
    if not return_maps:
        return []
    common = set(return_maps[0])
    for mapping in return_maps[1:]:
        common &= set(mapping)
    return sorted(common)


def sector_ad_line(sector_histories, sessions=20, expected=11):
    """Cumulative net advancing sector ETFs over the last `sessions` shared dates.

    Returns None unless every expected sector has history for those dates, so
    the line never silently drops a sector.
    """
    return_maps = [daily_total_returns(history) for history in sector_histories if history and not history.get("error")]
    if len(return_maps) < expected:
        return None
    dates = _common_dates(return_maps)[-sessions:]
    if len(dates) < sessions:
        return None
    net, cumulative, running = [], [], 0
    for date in dates:
        moves = [mapping[date] for mapping in return_maps]
        value = sum(move > 0 for move in moves) - sum(move < 0 for move in moves)
        running += value
        net.append(value)
        cumulative.append(running)
    return {
        "dates": dates,
        "net_advancing": net,
        "cumulative": cumulative,
        "universe": f"{expected} S&P sector ETFs",
        "basis": "Daily total return including dividends",
    }


def window_return(history, sessions):
    """Compounded total return over the last `sessions` sessions, in percent."""
    returns = daily_total_returns(history)
    dates = sorted(returns)[-sessions:]
    if len(dates) < sessions:
        return None
    factor = 1.0
    for date in dates:
        factor *= 1 + returns[date] / 100
    return (factor - 1) * 100


def relative_return(history, benchmark, sessions):
    """Percentage-point spread of `history` over `benchmark` for a window."""
    mine, theirs = window_return(history, sessions), window_return(benchmark, sessions)
    if mine is None or theirs is None:
        return None
    return round(mine - theirs, 2)


REGIME_RULE = (
    "Constructive: S&P 500 up, VIX down, all 11 sector ETFs reporting and at least 60% advancing. "
    "Defensive: S&P 500 down, VIX up, all 11 reporting and at most 40% advancing. Otherwise mixed."
)


def classify_regime(sp_pct, vix_pct, sector_moves, expected=11):
    """The generator's published risk-confirmation rule (build_editorial_context)."""
    if sp_pct is None or vix_pct is None:
        return "unavailable"
    full = len(sector_moves) == expected
    share = (sum(move > 0 for move in sector_moves) / len(sector_moves) * 100) if sector_moves else None
    if sp_pct > 0 and vix_pct < 0 and full and share is not None and share >= 60:
        return "risk_on_confirmed"
    if sp_pct < 0 and vix_pct > 0 and full and share is not None and share <= 40:
        return "risk_off_confirmed"
    return "mixed"


def regime_history(sp_history, vix_history, sector_histories, sessions=60, expected=11):
    """Apply the published rule to each of the last `sessions` S&P 500 sessions.

    Each day uses only that day's close-to-close moves, so no later data
    influences a classification. Days missing S&P or VIX data are marked
    unavailable rather than guessed.
    """
    sp_returns = daily_total_returns(sp_history or {})
    vix_returns = daily_total_returns(vix_history or {})
    sector_returns = [daily_total_returns(history or {}) for history in sector_histories]
    rows = []
    for date in sorted(sp_returns)[-sessions:]:
        moves = [returns[date] for returns in sector_returns if date in returns]
        sp_pct = sp_returns.get(date)
        vix_pct = vix_returns.get(date)
        rows.append({
            "date": date,
            "signal": classify_regime(sp_pct, vix_pct, moves, expected),
            "sp500_pct": sp_pct,
            "vix_pct": vix_pct,
            "sectors_positive": sum(move > 0 for move in moves),
            "sectors_valid": len(moves),
            "basis": "reconstructed",
        })
    return rows
