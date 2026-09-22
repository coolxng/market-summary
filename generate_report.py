import csv
import datetime
import io
import json
import math
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

from data_providers import build_market_calendar, build_verified_catalysts
from market_intelligence import build_data_quality, fetch_history_bundle


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"

SANITY_BOUNDS = {
    "GC=F": (1000, 8000),
    "CL=F": (20, 200),
    "BTC-USD": (1000, 500000),
    "ETH-USD": (50, 50000),
    "SOL-USD": (1, 10000),
    "XRP-USD": (0.01, 100),
    "^GSPC": (1000, 20000),
    "^IXIC": (1000, 50000),
    "^DJI": (5000, 200000),
    "^RUT": (500, 10000),
    "^VIX": (5, 150),
    "^MOVE": (20, 250),
    "^TNX": (0.1, 20),
    "^FVX": (0.1, 20),
    "^TYX": (0.1, 20),
    "^IRX": (0.0, 20),
    "DX-Y.NYB": (50, 200),
    "^N225": (10000, 100000),
    "^STOXX50E": (2000, 7000),
    "^FTSE": (4000, 15000),
    "^HSI": (10000, 50000),
}

FALLBACKS = {
    "GC=F": "GLD",
    "CL=F": "USO",
}

STOOQ_SYMBOLS = {
    "^GSPC": "^spx",
    "^IXIC": "^ndq",
    "^DJI": "^dji",
    "^VIX": "vi.c",
}

CORE_TICKERS = ("^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^TNX", "DX-Y.NYB")
SUMMARY_TILE_TICKERS = (
    ("S&P 500", "^GSPC"),
    ("Nasdaq", "^IXIC"),
    ("DJIA", "^DJI"),
    ("VIX", "^VIX"),
    ("10Y Yield", "^TNX"),
    ("DXY", "DX-Y.NYB"),
    ("Bitcoin", "BTC-USD"),
    ("Ethereum", "ETH-USD"),
)

US_REGULAR_CHART_TICKERS = (
    "^GSPC", "^IXIC", "^DJI", "^VIX", "^TNX", "DX-Y.NYB",
)
FULL_DAY_CHART_TICKERS = (
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
    "^N225", "^STOXX50E", "^FTSE", "^HSI",
)
SESSION_CHART_TICKERS = US_REGULAR_CHART_TICKERS + FULL_DAY_CHART_TICKERS
NY_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE_SETTLE_TIME = datetime.time(16, 15)
SESSION_LOOKBACK_DAYS = 15


# ─────────────────────────────────────────────
# DATA FETCHING
# ─────────────────────────────────────────────
def is_sane(ticker_symbol, value):
    if ticker_symbol not in SANITY_BOUNDS:
        return True
    lo, hi = SANITY_BOUNDS[ticker_symbol]
    return lo <= value <= hi


def current_market_now():
    return datetime.datetime.now(NY_TZ)


def normalize_market_now(now=None):
    now = now or current_market_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=NY_TZ)
    return now.astimezone(NY_TZ)


def latest_completed_session_candidate(now=None):
    """Return the latest date that could contain a completed U.S. session."""
    market_now = normalize_market_now(now)
    candidate = market_now.date()
    if market_now.time() < MARKET_CLOSE_SETTLE_TIME:
        candidate -= datetime.timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= datetime.timedelta(days=1)
    return candidate


def index_date(value):
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value)[:10])


def fetch_stooq_daily_rows(stooq_symbol, start_date, end_date):
    """Return validated Stooq daily CSV rows ordered by date."""
    query = urllib.parse.urlencode(
        {
            "s": stooq_symbol,
            "d1": start_date.strftime("%Y%m%d"),
            "d2": end_date.strftime("%Y%m%d"),
            "i": "d",
        }
    )
    request = urllib.request.Request(
        f"https://stooq.com/q/d/l/?{query}",
        headers={"User-Agent": "market-summary/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8-sig")

    rows = []
    for row in csv.DictReader(io.StringIO(payload)):
        date_value = row.get("Date")
        close_value = row.get("Close")
        if not date_value or close_value in (None, "", "N/D"):
            continue
        rows.append((index_date(date_value), row))
    rows.sort(key=lambda item: item[0])
    return rows


def fetch_recent_session_dates(candidate_date):
    """Resolve recent U.S. sessions from Yahoo, falling back to Stooq S&P 500 dates."""
    start_date = candidate_date - datetime.timedelta(days=SESSION_LOOKBACK_DAYS)
    try:
        history = yf.Ticker("^GSPC").history(
            start=start_date.isoformat(),
            end=(candidate_date + datetime.timedelta(days=1)).isoformat(),
            interval="1d",
        )
        history = history.dropna(subset=["Close"])
        dates = sorted({index_date(value) for value in history.index if index_date(value) <= candidate_date})
        if len(dates) >= 2:
            return dates
        print("  Yahoo session calendar returned fewer than two bars — trying Stooq")
    except Exception as exc:
        print(f"  Exception resolving Yahoo session calendar: {exc} — trying Stooq")

    stooq_rows = fetch_stooq_daily_rows(
        STOOQ_SYMBOLS["^GSPC"],
        start_date,
        candidate_date,
    )
    return sorted({row_date for row_date, _ in stooq_rows if row_date <= candidate_date})


def resolve_completed_sessions(now=None, session_dates=None):
    """Resolve the current and preceding completed sessions, including holidays."""
    candidate = latest_completed_session_candidate(now)
    available_dates = session_dates if session_dates is not None else fetch_recent_session_dates(candidate)
    completed_dates = sorted({date for date in available_dates if date <= candidate})
    if len(completed_dates) < 2:
        raise ValueError("Market data did not provide two completed U.S. trading sessions.")
    return completed_dates[-1], completed_dates[-2]


def snapshot_session_date(snapshot_path="report_snapshot.json"):
    path = Path(snapshot_path)
    if not path.exists():
        return None
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        value = snapshot.get("session_date")
        return datetime.date.fromisoformat(value) if value else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def has_new_session(session_date, snapshot_path="report_snapshot.json"):
    existing_session = snapshot_session_date(snapshot_path)
    return existing_session is None or session_date > existing_session


def validate_dataset(dataset, label, allow_zero=False):
    if dataset.get("error"):
        raise ValueError(f"{label} data unavailable: {dataset['error']}")
    end_price = float(dataset.get("end_price", 0.0) or 0.0)
    closes = dataset.get("closes") or []
    if not allow_zero and end_price <= 0:
        raise ValueError(f"{label} end price is invalid: {end_price}")
    if not closes:
        raise ValueError(f"{label} did not return any closes.")
    if dataset.get("ticker_used") and not is_sane(dataset["ticker_used"], end_price):
        raise ValueError(f"{label} end price failed sanity bounds: {end_price}")


def validate_core_datasets(
    dataset_map,
    expected_session_date=None,
    expected_previous_session_date=None,
):
    for ticker in CORE_TICKERS:
        validate_dataset(dataset_map[ticker], ticker)
        if expected_session_date and dataset_map[ticker].get("session_date") != expected_session_date.isoformat():
            raise ValueError(
                f"{ticker} did not return the completed session {expected_session_date.isoformat()}."
            )
        if (
            expected_previous_session_date
            and dataset_map[ticker].get("previous_session_date")
            != expected_previous_session_date.isoformat()
        ):
            raise ValueError(
                f"{ticker} did not compare against {expected_previous_session_date.isoformat()}."
            )


def fetch_daily_data(ticker_symbol, session_date, previous_session_date=None):
    """Fetch one completed session and its immediately preceding close."""
    tickers_to_try = [ticker_symbol]
    if ticker_symbol in FALLBACKS:
        tickers_to_try.append(FALLBACKS[ticker_symbol])

    for ticker_used in tickers_to_try:
        try:
            ticker = yf.Ticker(ticker_used)
            hist = ticker.history(
                start=(session_date - datetime.timedelta(days=SESSION_LOOKBACK_DAYS)).isoformat(),
                end=(session_date + datetime.timedelta(days=1)).isoformat(),
                interval="1d",
            )

            hist = hist.dropna(subset=["Close"])
            eligible_positions = [
                position
                for position, value in enumerate(hist.index)
                if index_date(value) <= session_date
            ]
            if len(eligible_positions) < 2:
                continue

            current_position = eligible_positions[-1]
            previous_position = eligible_positions[-2]
            current_date = index_date(hist.index[current_position])
            prior_date = index_date(hist.index[previous_position])
            current_row = hist.iloc[current_position]
            previous_row = hist.iloc[previous_position]
            end_price = round(float(current_row["Close"]), 2)
            prev_close = round(float(previous_row["Close"]), 2)
            session_open = round(float(current_row.get("Open", end_price)), 2)
            day_high = round(float(current_row.get("High", end_price)), 2)
            day_low = round(float(current_row.get("Low", end_price)), 2)

            if not is_sane(ticker_used, end_price):
                print(f"  Sanity check FAILED for {ticker_used}: end_price={end_price} — trying fallback")
                continue

            pct_change = ((end_price - prev_close) / prev_close) * 100 if prev_close else 0.0
            return {
                "dates": [prior_date.isoformat(), current_date.isoformat()],
                "closes": [prev_close, end_price],
                "end_price": end_price,
                "pct_change": round(pct_change, 2),
                "abs_change": round(end_price - prev_close, 2),
                "prev_close": prev_close,
                "session_open": session_open,
                "day_high": day_high,
                "day_low": day_low,
                "session_date": current_date.isoformat(),
                "previous_session_date": prior_date.isoformat(),
                "ticker_used": ticker_used,
                "data_source": "yahoo_finance",
                "source_symbol": ticker_used,
                "error": None,
            }
        except Exception as exc:
            print(f"  Exception fetching {ticker_used}: {exc}")

    stooq_symbol = STOOQ_SYMBOLS.get(ticker_symbol)
    if not stooq_symbol and re.fullmatch(r"[A-Z]{1,5}", ticker_symbol):
        # Stooq exposes most U.S. equities and ETFs as lower-case symbols with a .us suffix.
        stooq_symbol = f"{ticker_symbol.lower()}.us"
    if stooq_symbol:
        try:
            start_date = session_date - datetime.timedelta(days=SESSION_LOOKBACK_DAYS)
            rows = [
                (row_date, row)
                for row_date, row in fetch_stooq_daily_rows(stooq_symbol, start_date, session_date)
                if row_date <= session_date
            ]
            if len(rows) < 2:
                raise ValueError("Stooq returned fewer than two eligible daily bars")

            prior_date, previous_row = rows[-2]
            current_date, current_row = rows[-1]
            end_price = round(float(current_row["Close"]), 2)
            prev_close = round(float(previous_row["Close"]), 2)
            session_open = round(float(current_row.get("Open") or end_price), 2)
            day_high = round(float(current_row.get("High") or end_price), 2)
            day_low = round(float(current_row.get("Low") or end_price), 2)

            if not is_sane(ticker_symbol, end_price):
                raise ValueError(
                    f"Stooq sanity check failed for {ticker_symbol}: end_price={end_price}"
                )

            pct_change = ((end_price - prev_close) / prev_close) * 100 if prev_close else 0.0
            print(f"  Stooq fallback succeeded for {ticker_symbol} via {stooq_symbol}")
            return {
                "dates": [prior_date.isoformat(), current_date.isoformat()],
                "closes": [prev_close, end_price],
                "end_price": end_price,
                "pct_change": round(pct_change, 2),
                "abs_change": round(end_price - prev_close, 2),
                "prev_close": prev_close,
                "session_open": session_open,
                "day_high": day_high,
                "day_low": day_low,
                "session_date": current_date.isoformat(),
                "previous_session_date": prior_date.isoformat(),
                "ticker_used": ticker_symbol,
                "data_source": "stooq",
                "source_symbol": stooq_symbol,
                "error": None,
            }
        except Exception as exc:
            print(f"  Exception fetching Stooq fallback for {ticker_symbol}: {exc}")

    print(f"  All fetch attempts failed for {ticker_symbol}. Marking it unavailable.")
    # Unavailable rows keep null values so no consumer can mistake them for a flat session.
    return {
        "dates": [],
        "closes": [],
        "end_price": None,
        "pct_change": None,
        "abs_change": None,
        "prev_close": None,
        "session_open": None,
        "day_high": None,
        "day_low": None,
        "session_date": None,
        "previous_session_date": None,
        "ticker_used": ticker_symbol,
        "error": f"Data unavailable for {ticker_symbol}",
    }


def source_datetime(value):
    """Preserve the source exchange timezone when one is available."""
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime.datetime):
        value = datetime.datetime.fromisoformat(str(value))
    if value.tzinfo is None:
        return value.replace(tzinfo=NY_TZ)
    return value


def market_datetime(value):
    return source_datetime(value).astimezone(NY_TZ)


def fetch_recent_daily_chart_data(ticker_symbol, session_date):
    """Return a short multi-session fallback path when intraday data is unavailable."""
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(
        start=(session_date - datetime.timedelta(days=12)).isoformat(),
        end=(session_date + datetime.timedelta(days=1)).isoformat(),
        interval="1d",
    )
    hist = hist.dropna(subset=["Close"])
    positions = [
        position
        for position, value in enumerate(hist.index)
        if index_date(value) <= session_date
    ][-5:]
    if len(positions) < 3:
        raise ValueError("Not enough recent daily bars for chart fallback")

    dates = [index_date(hist.index[position]) for position in positions]
    return {
        "times": [date.strftime("%b %d").replace(" 0", " ") for date in dates],
        "closes": [round(float(hist["Close"].iloc[position]), 2) for position in positions],
        "source": "daily_5d_fallback",
        "session_date": session_date.isoformat(),
        "error": None,
    }


def fetch_daily_chart_data(
    ticker_symbol,
    session_date,
    fallback_data=None,
    *,
    regular_hours=True,
    prefer_multi_day_fallback=False,
):
    """Fetch a verified intraday path for the requested market session.

    U.S. market charts are restricted to 9:30 a.m.–4:00 p.m. New York time.
    Global and crypto charts preserve the source instrument timezone and use the
    full source-calendar day so their paths are not incorrectly clipped to U.S. hours.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(
            start=session_date.isoformat(),
            end=(session_date + datetime.timedelta(days=1)).isoformat(),
            interval="5m",
            prepost=False,
        )

        hist = hist.dropna(subset=["Close"])
        chart_positions = []
        chart_times = []
        for position, value in enumerate(hist.index):
            source_timestamp = source_datetime(value)
            if regular_hours:
                timestamp = source_timestamp.astimezone(NY_TZ)
                include = (
                    timestamp.date() == session_date
                    and datetime.time(9, 30) <= timestamp.time() <= datetime.time(16, 0)
                )
            else:
                timestamp = source_timestamp
                include = timestamp.date() == session_date

            if include:
                chart_positions.append(position)
                chart_times.append(timestamp)

        if len(chart_positions) < 3:
            raise ValueError("Not enough intraday data returned")

        return {
            "times": [timestamp.strftime("%I:%M %p").lstrip("0") for timestamp in chart_times],
            "closes": [round(float(hist["Close"].iloc[position]), 2) for position in chart_positions],
            "source": "intraday_5m",
            "session_date": session_date.isoformat(),
            "error": None,
        }
    except Exception as exc:
        if prefer_multi_day_fallback:
            try:
                chart = fetch_recent_daily_chart_data(ticker_symbol, session_date)
                print(
                    f"  Intraday chart unavailable for {ticker_symbol}: {exc} "
                    "— using recent daily path"
                )
                return chart
            except Exception as fallback_exc:
                print(
                    f"  Intraday and recent-daily chart data unavailable for {ticker_symbol}: "
                    f"{fallback_exc}"
                )
                return {
                    "times": [],
                    "closes": [],
                    "source": "daily_5d_fallback",
                    "session_date": session_date.isoformat(),
                    "error": str(fallback_exc),
                }

        print(
            f"  Exception fetching intraday chart data for {ticker_symbol}: "
            f"{exc} — using session open/close fallback"
        )
        fallback = fallback_data or fetch_daily_data(ticker_symbol, session_date)
        session_open = fallback.get("session_open") or fallback.get("end_price", 0.0)
        session_close = fallback.get("end_price", 0.0)
        return {
            "times": ["9:30 AM", "4:00 PM"],
            "closes": [session_open, session_close],
            "source": "daily_ohlc_fallback",
            "session_date": session_date.isoformat(),
            "error": fallback.get("error"),
        }


# ─────────────────────────────────────────────
# GROUNDED EDITORIAL BRIEF
# ─────────────────────────────────────────────
def should_use_ai():
    return bool(ANTHROPIC_API_KEY)


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def build_editorial_context(datasets, sectors, megacaps, charts, spy, rsp, session_date):
    """Only verified same-session observations enter the editorial evidence pool.

    Sector breadth is an ETF proxy, not constituent advance/decline breadth.
    Return spreads are percentage points; Treasury level changes become basis points.
    No news/calendar feed is present, so no event or causal claims are eligible.
    """
    session = session_date.isoformat()
    previous = datasets['^GSPC'].get('previous_session_date')

    def compact(row):
        if (row.get('error') or row.get('session_date') != session
                or row.get('previous_session_date') != previous
                or not all(finite_number(row.get(k)) for k in ('end_price', 'pct_change', 'prev_close'))
                or row['end_price'] <= 0 or row['prev_close'] <= 0):
            return None
        return {k: row[k] for k in ('end_price', 'pct_change', 'prev_close', 'session_date',
                                    'previous_session_date', 'ticker_used') if k in row}

    market = {k: compact(v) for k, v in datasets.items()}
    sector_rows = {k: compact(v) for k, v in sectors.items()}
    stocks = {k: compact(v['result']) for k, v in megacaps.items()}
    market.update({'SPY': compact(spy), 'RSP': compact(rsp)})
    cards = {}
    metrics = {}

    def add(key, group, headline, observed, interpretation, watch):
        cards[key] = dict(group=group, headline=headline, observed=observed,
                          interpretation=interpretation, watch=watch)

    def pct(symbol):
        row = market.get(symbol)
        return row['pct_change'] if row else None

    sp, nd, rut, vix = (pct(k) for k in ('^GSPC', '^IXIC', '^RUT', '^VIX'))
    if sp is not None:
        add('index', 'market', 'Equities close higher' if sp > 0 else 'Equities close lower' if sp < 0 else 'Equities finish flat',
            f'S&P 500 {sp:+.2f}% at the close.',
            'The headline index alone does not establish the strength of participation.',
            'Check whether equal-weight performance and sector participation confirm the next index move.')
    for key, value, label in [('nasdaq_gap', nd, 'Nasdaq'), ('small_cap_gap', rut, 'Russell 2000')]:
        if sp is not None and value is not None:
            gap = round(value - sp, 4); metrics[key + '_pp'] = gap
            add(key, 'market', f'{label} {"outpaces" if gap > 0 else "trails" if gap < 0 else "matches"} the broad index',
                f'{label} {value:+.2f}% versus S&P 500 {sp:+.2f}%, a {gap:+.2f} percentage-point spread.',
                'The indices show uneven participation.' if abs(gap) >= .25 else 'Index returns were closely aligned; the sector split offers a finer participation check.',
                f'Check whether {label} relative strength persists or converges with the S&P 500.')
    valid_sectors = sorted(((k, v['pct_change']) for k, v in sector_rows.items() if v), key=lambda x: x[1], reverse=True)
    share = None
    if valid_sectors:
        count = len(valid_sectors); positive = sum(v > 0 for _, v in valid_sectors)
        share = positive / count * 100
        metrics['sector_breadth'] = {'positive': positive, 'valid': count, 'expected': len(sectors),
                                    'positive_share_pct': round(share, 2), 'proxy': 'sector ETF participation'}
        top, bottom = valid_sectors[0], valid_sectors[-1]
        metrics['sector_dispersion_pp'] = round(top[1] - bottom[1], 4)
        metrics['sector_relative_to_sp_pp'] = {k: round(v-sp, 4) for k,v in valid_sectors} if sp is not None else {}
        add('breadth', 'regime', 'Participation broadens the read' if share >= 60 else 'Participation warrants caution',
            f'{positive} of {count} available sector ETFs advanced ({share:.1f}%); coverage {count}/{len(sectors)}.',
            'Sector ETF participation was broad.' if share >= 60 else 'Sector ETF participation was mixed.' if share >= 40 else 'Most available sector ETFs did not advance.',
            f'Participation above {positive}/{count} advancing sector ETFs would broaden the next-session reading; lower participation would weaken it.' if positive < count else f'Test whether all {count} available sector ETFs continue to advance or participation narrows.')
        add('sectors', 'sector', f'{top[0]} ranks among sector leaders' if top[1] != bottom[1] else 'Sector returns finish level',
            (f'{top[0]} {top[1]:+.2f}% ranked highest; {bottom[0]} {bottom[1]:+.2f}% ranked lowest, separated by {top[1]-bottom[1]:.2f} percentage points.' if top[1] != bottom[1] else f'All {count} available sector ETF returns matched at {top[1]:+.2f}%.'),
            'The return spread identifies relative leadership, not fund flows or a verified catalyst.',
            f'Check whether {top[0]} retains relative strength and whether {bottom[0]} closes the gap.')
        for i,(name,value) in enumerate(valid_sectors):
            add(f'sector_{i}', 'sector', f'{name} in focus',
                f'{name} {value:+.2f}%'+(f', {value-sp:+.2f} percentage points versus the S&P 500.' if sp is not None else '.'),
                'Relative return identifies positioning exposure; it does not establish why the sector moved.',
                f'Check whether {name} sustains its relative performance next session.')
    if pct('RSP') is not None and pct('SPY') is not None:
        gap = pct('RSP') - pct('SPY'); metrics['equal_weight_minus_cap_weight_pp'] = round(gap,4)
        add('weighting','regime','Equal weight leads' if gap > 0 else 'Cap weight leads' if gap < 0 else 'Weighting offers no separation',
            f'RSP {pct("RSP"):+.2f}% versus SPY {pct("SPY"):+.2f}%; equal weight minus cap weight {gap:+.2f} percentage points.',
            'Equal-weight outperformance supports a broader participation reading.' if gap > 0 else 'Cap-weight outperformance is consistent with concentrated leadership, not a measured attribution of index contributions.' if gap < 0 else 'Equal and cap weighting delivered matching returns.',
            f'Use the {gap:+.2f} percentage-point RSP-minus-SPY spread as the reference: a rise favors broader participation; a decline favors cap-weight leadership.')
    if sp is not None and vix is not None:
        tone = 'risk_on_confirmed' if sp > 0 and vix < 0 and share is not None and len(valid_sectors) == len(sectors) and share >= 60 else 'risk_off_confirmed' if sp < 0 and vix > 0 and share is not None and len(valid_sectors) == len(sectors) and share <= 40 else 'mixed'
        metrics['risk_confirmation'] = {'signal':tone,'rule':'Full sector coverage + S&P direction + opposite VIX direction + sector positive share >=60% or <=40%; otherwise mixed'}
        add('risk','regime','Risk signals align' if tone != 'mixed' else 'Risk signals remain mixed',
            f'S&P 500 {sp:+.2f}%; VIX {vix:+.2f}%'+(f'; positive sector share {share:.1f}%.' if share is not None else '; sector participation unavailable.'),
            {'risk_on_confirmed':'Equities, volatility and sector participation support a risk-on reading.', 'risk_off_confirmed':'Equities, volatility and sector participation support a defensive reading.', 'mixed':'The equity, volatility and participation checks do not give a unanimous directional signal.'}[tone],
            'Look for agreement between equity direction, volatility and sector participation before treating the move as broadly confirmed.')
    if market.get('^TNX'):
        row=market['^TNX'];bps=(row['end_price']-row['prev_close'])*100;metrics['ten_year_change_bp']=round(bps,4)
        add('rates','macro','Yields frame the valuation read',
            f'The ten-year yield closed at {row["end_price"]:.2f}%, a {bps:+.2f} basis-point change.',
            'Higher yields can raise the valuation hurdle for duration-sensitive equities; co-movement is not proof of causality.' if bps > 0 else 'Lower yields can ease the valuation hurdle for duration-sensitive equities; co-movement is not proof of causality.' if bps < 0 else 'An unchanged yield offers little directional confirmation.',
            f'Use {row["end_price"]:.2f}% as the ten-year closing reference; test whether a move above it coincides with weaker technology relative returns.')
    for key,a,b,label in [('dollar_gold','DX-Y.NYB','GC=F','Dollar and gold'),('oil_equities','CL=F','^GSPC','Oil and equities'),('crypto_equities','BTC-USD','^IXIC','Bitcoin and Nasdaq')]:
        if pct(a) is not None and pct(b) is not None:
            same = pct(a)*pct(b)>0
            metrics[key]={'same_direction':same,'first_pct':pct(a),'second_pct':pct(b),'window':'same requested dates; different market closing times'}
            add(key,'macro',label+' in context',
                f'{market[a]["ticker_used"]} {pct(a):+.2f}% and {market[b]["ticker_used"]} {pct(b):+.2f}% over their reported sessions.',
                'The moves point in the same direction, but a single session does not establish correlation or a shared cause.' if same else 'The moves do not give a common directional signal; differing session clocks limit cross-asset conclusions.',
                f'Test whether {market[a]["ticker_used"]} ({pct(a):+.2f}%) and {market[b]["ticker_used"]} ({pct(b):+.2f}%) retain their directional relationship in the next comparable window.')
    valid_stocks={k:v for k,v in stocks.items() if v}
    if valid_stocks:
        ordered=sorted(valid_stocks, key=lambda k:valid_stocks[k]['pct_change'],reverse=True)
        best,worst=ordered[0],ordered[-1]
        positives=[max(v['pct_change'],0) for v in valid_stocks.values()]
        metrics['megacap_sample']={'valid':len(ordered),'expected':len(stocks),'positive':sum(v>0 for v in positives),
            'dispersion_pp':round(valid_stocks[best]['pct_change']-valid_stocks[worst]['pct_change'],4),
            'leader_share_of_positive_returns_pct':round(max(positives)/sum(positives)*100,2) if sum(positives)>0 else None,
            'limitation':'unweighted selected-stock sample; not index contribution or portfolio weight'}
        add('megacaps','megacap','Selected technology leaders diverge' if valid_stocks[best]['pct_change'] != valid_stocks[worst]['pct_change'] else 'Selected technology returns match',
            (f'{best} {valid_stocks[best]["pct_change"]:+.2f}% ranked highest in the available technology sample; {worst} {valid_stocks[worst]["pct_change"]:+.2f}% ranked lowest.' if valid_stocks[best]['pct_change'] != valid_stocks[worst]['pct_change'] else f'The {len(ordered)} available technology-stock returns matched at {valid_stocks[best]["pct_change"]:+.2f}%.'),
            'Dispersion in this selected sample distinguishes stock-specific exposure from the headline technology narrative; no catalyst is verified.',
            f'Compare next-session participation with today’s {sum(v > 0 for v in positives)}/{len(ordered)} advancing technology names; fewer advancers would narrow leadership.')
    for symbol,row in valid_stocks.items():
        move=row['pct_change']
        add('stock_'+symbol,'megacap',symbol+' relative performance',
            f'{symbol} {move:+.2f}%'+(f', {move-nd:+.2f} percentage points versus Nasdaq.' if nd is not None else '.'),
            'Relative price strength is observable; earnings, AI demand and order-flow explanations are not established by these data.',
            f'Check whether {symbol} maintains relative strength alongside the broader technology sample.')
    for key,symbol in [('nikkei','^N225'),('stoxx','^STOXX50E'),('ftse','^FTSE'),('hsi','^HSI'),('btc','BTC-USD'),('eth','ETH-USD'),('sol','SOL-USD'),('xrp','XRP-USD')]:
        if market.get(symbol):
            add(key,'global' if key in ('nikkei','stoxx','ftse','hsi') else 'crypto',symbol+' session read',
                f'{symbol} {pct(symbol):+.2f}% for the reported session.',
                'Local closing times differ from the U.S. equity close; this is context, not synchronized confirmation.',
                f'Check whether {symbol} maintains its direction in the next comparable observation window.')
    intraday={}
    for symbol,chart in charts.items():
        values=chart.get('closes',[])
        if (chart.get('error') or chart.get('source')!='intraday_5m' or chart.get('session_date')!=session
                or len(values)<3 or not all(finite_number(x) and x>0 for x in values)):
            continue
        high,low=max(values),min(values)
        intraday[symbol]={'first_to_last_pct':round((values[-1]/values[0]-1)*100,4),
                         'close_location_pct':round((values[-1]-low)/(high-low)*100,2) if high>low else None,
                         'source':'sampled intraday closes, not exchange OHLC extremes'}
    metrics['intraday']=intraday
    if '^GSPC' in intraday:
        move=intraday['^GSPC']['first_to_last_pct'];location=intraday['^GSPC']['close_location_pct']
        add('intraday','market','The session path qualifies the close',
            f'S&P 500 moved {move:+.2f}% from the first to last available intraday sample.'+(f' The last sample was at {location:.1f}% of the sampled closing-price range.' if location is not None else ' The sampled range was flat.'),
            'The path distinguishes intraday follow-through from the previous-close return; sampled bars do not establish an event catalyst.',
            'Check whether the next session extends the closing direction or reverses it.')
    context={'session_date':session,'market':market,'sectors':sector_rows,'megacaps':stocks,'derived_metrics':metrics,
             'limitations':['Verified catalysts and calendar items are published separately with sources; never attribute price moves to events.',
                            'Missing/stale/error rows are null; no imputed zero returns.',
                            'Sector ETFs and the selected technology sample are proxies, not whole-market breadth.',
                            'Futures fallback instruments remain explicitly labeled; global and crypto clocks differ.']}
    return context,cards


EDITORIAL_GROUPS = {'headline':{'market','regime','sector'},'opening_summary':{'market','regime','sector','megacap'},'regime':{'regime'},
                    'sector_leadership':{'sector'},'megacap_leadership':{'megacap'},
                    'macro_read':{'macro'},'investor_takeaway':{'regime','market'},'watchlist':None}


def editorial_choices(cards):
    return {key:[cid for cid,card in cards.items() if groups is None or card['group'] in groups]
            for key,groups in EDITORIAL_GROUPS.items()}


def default_editorial_plan(cards):
    choices=editorial_choices(cards)
    priority=['risk','weighting','breadth','index','nasdaq_gap','small_cap_gap','intraday',
              'sectors','megacaps','rates','dollar_gold','oil_equities','crypto_equities']
    preferred = {'headline':['weighting','risk','index'], 'opening_summary':['index','sectors'],
                 'regime':['risk','breadth'], 'sector_leadership':['sectors'],
                 'megacap_leadership':['megacaps'], 'macro_read':['rates'],
                 'investor_takeaway':['weighting','breadth'], 'watchlist':['breadth','rates','megacaps']}
    result = {}
    for key, ids in choices.items():
        order = preferred[key] + priority
        ranked = sorted(ids, key=lambda cid: order.index(cid) if cid in order else len(order))
        result[key] = ranked[:3 if key == 'watchlist' else 2 if key == 'opening_summary' else 1]
    return result


def editorial_schema(cards):
    selection_properties = {
        key: {'type': 'array', 'items': {'type': 'string', 'enum': ids or ['unavailable']}}
        for key, ids in editorial_choices(cards).items()
    }
    interpretation_properties = {
        key: {'type': 'string'} for key in AI_INTERPRETATION_SECTIONS
    }
    return {
        'type': 'object',
        'properties': {
            'selection': {
                'type': 'object',
                'properties': selection_properties,
                'required': list(selection_properties),
                'additionalProperties': False,
            },
            'headline_text': {'type': 'string'},
            'interpretations': {
                'type': 'object',
                'properties': interpretation_properties,
                'required': list(interpretation_properties),
                'additionalProperties': False,
            },
        },
        'required': ['selection', 'headline_text', 'interpretations'],
        'additionalProperties': False,
    }


def parse_editorial_plan(raw,cards):
    def unique_keys(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate key')
            result[key]=value
        return result
    plan=json.loads(raw,object_pairs_hook=unique_keys)
    if not isinstance(plan,dict) or set(plan)!=set(EDITORIAL_GROUPS):raise ValueError('invalid sections')
    for key,allowed in editorial_choices(cards).items():
        ids=plan[key];limit=3 if key=='watchlist' else 2 if key=='opening_summary' else 1
        if (not isinstance(ids,list) or len(ids)>limit or (bool(allowed) and not ids)
                or any(not isinstance(cid,str) or cid not in allowed for cid in ids)
                or len(set(ids))!=len(ids)):
            raise ValueError('invalid evidence selection')
    return plan


AI_INTERPRETATION_SECTIONS = (
    'regime',
    'sector_leadership',
    'megacap_leadership',
    'macro_read',
    'investor_takeaway',
)


def validate_editorial_prose(value, field, max_chars):
    if not isinstance(value, str):
        raise ValueError(f'{field} must be text')
    text = re.sub(r'\s+', ' ', value).strip()
    if not text or len(text) > max_chars or '\n' in value or '\r' in value:
        raise ValueError(f'invalid {field} length')
    # AI-written text is qualitative only. All numbers and factual observations
    # continue to come from the server-side evidence cards.
    if re.search(r'[\d%$]', text):
        raise ValueError(f'{field} cannot introduce numeric facts')
    lower = f' {text.lower()} '
    forbidden = (
        ' because ', ' due to ', ' driven by ', ' caused by ', ' on news ',
        ' after the ', ' following the ', ' announced ', ' reported ',
        ' will ', ' likely ', ' should ', ' forecast ', ' predict ',
        ' tomorrow ', ' next week ',
    )
    if any(phrase in lower for phrase in forbidden):
        raise ValueError(f'{field} cannot introduce causes, events, or predictions')
    return text


def parse_editorial_response(raw, cards):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result

    response = json.loads(raw, object_pairs_hook=unique_keys)
    expected = {'selection', 'headline_text', 'interpretations'}
    if not isinstance(response, dict) or set(response) != expected:
        raise ValueError('invalid editorial response')

    selection = response['selection']
    if not isinstance(selection, dict):
        raise ValueError('selection must be an object')
    plan = parse_editorial_plan(json.dumps(selection, separators=(',', ':')), cards)

    headline = response['headline_text']
    if not isinstance(headline, str):
        raise ValueError('headline_text must be text')
    if plan['headline']:
        headline = validate_editorial_prose(headline, 'headline_text', 140)
    elif headline.strip():
        raise ValueError('headline text requires selected evidence')

    interpretations = response['interpretations']
    if not isinstance(interpretations, dict) or set(interpretations) != set(AI_INTERPRETATION_SECTIONS):
        raise ValueError('invalid interpretations object')
    clean_interpretations = {}
    for key in AI_INTERPRETATION_SECTIONS:
        value = interpretations[key]
        if not isinstance(value, str):
            raise ValueError(f'{key} interpretation must be text')
        if plan[key]:
            clean_interpretations[key] = validate_editorial_prose(value, key, 320)
        elif value.strip():
            raise ValueError(f'{key} interpretation requires selected evidence')
        else:
            clean_interpretations[key] = ''

    return plan, {
        'headline_text': headline.strip(),
        'interpretations': clean_interpretations,
    }


INDEX_MOVE_PATTERN = re.compile(r'S&P 500 [+-]\d+\.\d+%')


def compose_observed(cards, card_ids):
    """Join observed facts without repeating an index move already stated."""
    seen = set()
    parts = []
    for cid in card_ids:
        text = cards[cid]['observed']
        for token in INDEX_MOVE_PATTERN.findall(text):
            if token in seen:
                text = text.replace(f'{token}; ', '', 1)
            seen.add(token)
        parts.append(text)
    return ' '.join(parts)


def generate_editorial(context,cards):
    """Use one bounded Claude request for selection plus qualitative writing.

    Claude may choose evidence and rewrite the headline/interpretation language, but
    all observed facts, numbers, watch conditions, and published market data are
    assembled from validated server-side evidence cards.
    """
    plan = default_editorial_plan(cards)
    ai_prose = None
    status = 'missing_key'
    if should_use_ai():
        try:
            payload = {
                'model': ANTHROPIC_MODEL,
                'max_tokens': 1200,
                'system': (
                    'You are the editor of a concise institutional market-close note. '
                    'First select the most material evidence-backed angles from the supplied catalog. '
                    'Then improve only the headline and interpretation wording for the selected evidence. '
                    'Observed facts, numbers, opening-summary facts, and watch conditions are rendered by code and are not yours to rewrite. '
                    'For headline_text, write a crisp 4-12 word market headline with no digits, prices, percentages, dates, unsupported named entities, events, causes, or forecasts. '
                    'For each interpretation string, write one concise institutional sentence that rephrases only the selected card interpretation. '
                    'Do not add numbers, prices, percentages, dates, events, catalysts, causal claims, predictions, recommendations, or facts not present in the selected evidence. '
                    'Do not use because, due to, driven by, caused by, will, likely, should, forecast, or predict. '
                    'If a section has no eligible selected evidence, return an empty string for its interpretation. '
                    'Return only the specified JSON. Keep selection rules unchanged: one ID per section, one or two for opening_summary, '
                    'and three distinct watchlist IDs spanning participation, rates/cross-assets and leadership when available.'
                ),
                'messages': [{
                    'role': 'user',
                    'content': json.dumps(
                        {'context': context, 'catalog': cards, 'eligible': editorial_choices(cards)},
                        allow_nan=False,
                        separators=(',', ':'),
                    ),
                }],
                'output_config': {'format': {'type': 'json_schema', 'schema': editorial_schema(cards)}},
            }
            request = urllib.request.Request(
                ANTHROPIC_API_URL,
                data=json.dumps(payload).encode(),
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': ANTHROPIC_API_KEY,
                    'anthropic-version': '2023-06-01',
                },
                method='POST',
            )
            with urllib.request.urlopen(request, timeout=35) as response:
                body = json.loads(response.read(100_001).decode())
            if body.get('stop_reason') != 'end_turn':
                raise ValueError('incomplete response')
            content = body.get('content')
            if not isinstance(content, list) or not content or any(block.get('type') != 'text' for block in content):
                raise ValueError('unexpected response blocks')
            plan, ai_prose = parse_editorial_response(
                ''.join(block['text'] for block in content),
                cards,
            )
            status = 'validated'
        except Exception:
            # Never echo response bodies, exception text or credentials into logs/artifacts.
            print('Claude editorial request unavailable or invalid; using grounded fallback.')
            status = 'request_or_validation_failed'

    def render(key, field):
        if field == 'observed':
            return compose_observed(cards, plan[key])
        return ' '.join(cards[cid][field] for cid in plan[key])

    deterministic_headline = render('headline', 'headline')
    editorial = {
        'headline': ai_prose['headline_text'] if ai_prose else deterministic_headline,
        'opening_summary': render('opening_summary', 'observed'),
        'watchlist': [cards[cid]['watch'] for cid in plan['watchlist']],
    }
    for key in AI_INTERPRETATION_SECTIONS:
        observed = render(key, 'observed') or 'Verified evidence unavailable.'
        deterministic_interpretation = render(key, 'interpretation') or 'No interpretation without verified evidence.'
        ai_interpretation = ai_prose['interpretations'][key] if ai_prose and plan[key] else ''
        editorial[key] = {
            'observed': observed,
            'interpretation': ai_interpretation or deterministic_interpretation,
        }

    return editorial, {
        'mode': 'ai' if status == 'validated' else 'deterministic_fallback',
        'status': status,
        'contract_version': 2,
        'model': ANTHROPIC_MODEL if status == 'validated' else None,
        'selection': plan,
        'ai_writing': status == 'validated',
        'writing_scope': ['headline', 'interpretations'] if status == 'validated' else [],
    }


def fmt_date(dt, include_day=True):
    if include_day:
        return f"{dt.strftime('%b')} {dt.day}"
    return f"{dt.strftime('%B')} {dt.day}, {dt.strftime('%Y')}"


# ─────────────────────────────────────────────
# REPORT SNAPSHOT GENERATOR
# ─────────────────────────────────────────────
def generate_html(now=None, snapshot_path="report_snapshot.json", archive_root="public/reports"):
    session_date, previous_session_date = resolve_completed_sessions(now)
    if not has_new_session(session_date, snapshot_path):
        print(f"No new completed trading session after {session_date.isoformat()}; leaving artifacts unchanged.")
        return False

    print(f"Fetching market data for completed session {session_date.isoformat()}...")

    ticker_symbols = (
        "^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^MOVE", "^TNX", "^FVX", "^TYX", "^IRX", "DX-Y.NYB",
        "GC=F", "CL=F", "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
        "^N225", "^STOXX50E", "^FTSE", "^HSI", "HYG", "LQD", "TIP",
    )
    datasets = {
        symbol: fetch_daily_data(symbol, session_date, previous_session_date)
        for symbol in ticker_symbols
    }
    validate_core_datasets(
        datasets,
        expected_session_date=session_date,
        expected_previous_session_date=previous_session_date,
    )

    full_date = fmt_date(
        datetime.datetime.combine(session_date, datetime.time(), tzinfo=NY_TZ),
        include_day=False,
    )

    sectors = {
        "Technology (XLK)": "XLK",
        "Financials (XLF)": "XLF",
        "Energy (XLE)": "XLE",
        "Healthcare (XLV)": "XLV",
        "Industrials (XLI)": "XLI",
        "Cons. Discretionary (XLY)": "XLY",
        "Cons. Staples (XLP)": "XLP",
        "Real Estate (XLRE)": "XLRE",
        "Utilities (XLU)": "XLU",
        "Materials (XLB)": "XLB",
        "Comm. Services (XLC)": "XLC",
    }
    sector_results = {
        name: fetch_daily_data(ticker, session_date, previous_session_date)
        for name, ticker in sectors.items()
    }
    sector_perf = {
        name: result["pct_change"]
        for name, result in sector_results.items()
        if not result.get("error")
    }
    sorted_sectors = sorted(sector_perf.items(), key=lambda item: item[1], reverse=True)
    if len(sorted_sectors) < 4:
        raise ValueError("Insufficient sector data to build the daily report.")

    all_sectors_ranked = sorted_sectors
    top_sectors = sorted_sectors[:4]
    bottom_sectors = sorted_sectors[-4:]

    session_charts = {
        symbol: fetch_daily_chart_data(
            symbol,
            session_date,
            fallback_data=datasets[symbol],
            regular_hours=symbol in US_REGULAR_CHART_TICKERS,
            prefer_multi_day_fallback=symbol in FULL_DAY_CHART_TICKERS,
        )
        for symbol in SESSION_CHART_TICKERS
    }
    megacaps = {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "NVDA": "Nvidia",
        "AMZN": "Amazon",
        "META": "Meta Platforms",
        "SNDK": "SanDisk",
        "AMD": "Advanced Micro Devices",
        "INTC": "Intel",
        "MU": "Micron Technology",
    }
    megacap_data = {}
    for ticker, company in megacaps.items():
        result = fetch_daily_data(ticker, session_date, previous_session_date)
        megacap_data[ticker] = {
            "name": company,
            "result": result,
            "session_chart": fetch_daily_chart_data(
                ticker,
                session_date,
                fallback_data=result,
            ),
        }
    spy = fetch_daily_data("SPY", session_date, previous_session_date)
    rsp = fetch_daily_data("RSP", session_date, previous_session_date)

    asset_catalog = [
        {"slug": "spx", "symbol": "^GSPC", "name": "S&P 500", "category": "Index"},
        {"slug": "nasdaq", "symbol": "^IXIC", "name": "Nasdaq Composite", "category": "Index"},
        {"slug": "dow", "symbol": "^DJI", "name": "Dow Jones", "category": "Index"},
        {"slug": "russell-2000", "symbol": "^RUT", "name": "Russell 2000", "category": "Index"},
        {"slug": "vix", "symbol": "^VIX", "name": "CBOE Volatility Index", "category": "Volatility"},
        {"slug": "us-10y", "symbol": "^TNX", "name": "U.S. 10-Year Treasury Yield", "category": "Rates"},
        {"slug": "dxy", "symbol": "DX-Y.NYB", "name": "U.S. Dollar Index", "category": "FX"},
        {"slug": "gold", "symbol": "GC=F", "name": "Gold", "category": "Commodity"},
        {"slug": "wti", "symbol": "CL=F", "name": "WTI Crude", "category": "Commodity"},
        {"slug": "move", "symbol": "^MOVE", "name": "ICE BofA MOVE Index", "category": "Volatility"},
        {"slug": "bitcoin", "symbol": "BTC-USD", "name": "Bitcoin", "category": "Crypto"},
        {"slug": "ethereum", "symbol": "ETH-USD", "name": "Ethereum", "category": "Crypto"},
        {"slug": "solana", "symbol": "SOL-USD", "name": "Solana", "category": "Crypto"},
        {"slug": "xrp", "symbol": "XRP-USD", "name": "XRP", "category": "Crypto"},
    ]
    asset_catalog.extend(
        {"slug": ticker.lower(), "symbol": ticker, "name": company, "category": "Equity"}
        for ticker, company in megacaps.items()
    )
    asset_catalog.extend(
        {
            "slug": ticker.lower(),
            "symbol": ticker,
            "name": name.split(" (")[0],
            "category": "Sector ETF",
        }
        for name, ticker in sectors.items()
    )

    history_symbols = [entry["symbol"] for entry in asset_catalog] + ["SPY", "RSP", "QQQ", "IWM", "HYG", "LQD", "TIP", "^FVX", "^TYX"]
    asset_history = fetch_history_bundle(history_symbols, session_date)

    spy_history = asset_history.get("SPY", {})
    sector_trend = {}
    for sector_name, ticker in sectors.items():
        history = asset_history.get(ticker, {})
        sector_trend[sector_name] = {
            "symbol": ticker,
            "returns": history.get("returns", {}),
            "above_moving_average": history.get("above_moving_average", {}),
        }

    def participation(window):
        states = [
            row["above_moving_average"].get(window)
            for row in sector_trend.values()
            if row.get("above_moving_average", {}).get(window) is not None
        ]
        if not states:
            return None
        return {
            "above": sum(bool(value) for value in states),
            "valid": len(states),
            "share_pct": round(sum(bool(value) for value in states) / len(states) * 100, 1),
        }

    spy_returns = spy_history.get("returns", {})
    relative_strength = {}
    for sector_name, row in sector_trend.items():
        relative_strength[sector_name] = {}
        for window in ("5d", "1m", "3m", "ytd"):
            sector_return = row.get("returns", {}).get(window)
            benchmark_return = spy_returns.get(window)
            relative_strength[sector_name][window] = (
                round(sector_return - benchmark_return, 2)
                if isinstance(sector_return, (int, float)) and isinstance(benchmark_return, (int, float))
                else None
            )

    tracked_breadth_symbols = list(dict.fromkeys([*sectors.values(), *megacaps.keys(), "SPY", "RSP", "QQQ", "IWM"]))
    tracked_highs = 0
    tracked_lows = 0
    tracked_valid = 0
    for symbol in tracked_breadth_symbols:
        closes = asset_history.get(symbol, {}).get("closes", [])
        if len(closes) < 20:
            continue
        window = closes[-20:]
        current_close = window[-1]
        tracked_valid += 1
        if current_close >= max(window):
            tracked_highs += 1
        if current_close <= min(window):
            tracked_lows += 1

    market_internals = {
        "trend_participation": {
            "above_20d": participation("20d"),
            "above_50d": participation("50d"),
            "above_200d": participation("200d"),
            "universe": "11 S&P sector ETFs",
        },
        "tracked_high_low": {
            "new_20d_highs": tracked_highs,
            "new_20d_lows": tracked_lows,
            "valid": tracked_valid,
            "universe": "11 sector ETFs + tracked mega-caps + SPY/RSP/QQQ/IWM",
        },
        "sector_relative_strength_vs_spy": relative_strength,
        "benchmark_returns": spy_returns,
        "limitation": "Trend participation and new-high/new-low counts use transparent tracked universes, not full NYSE/Nasdaq constituent breadth.",
    }

    rates_credit = {
        "3m": datasets.get("^IRX"),
        "5y": datasets.get("^FVX"),
        "10y": datasets.get("^TNX"),
        "30y": datasets.get("^TYX"),
        "hyg": datasets.get("HYG"),
        "lqd": datasets.get("LQD"),
        "tip": datasets.get("TIP"),
        "move": datasets.get("^MOVE"),
    }
    if datasets.get("^TNX") and datasets.get("^FVX") and not datasets["^TNX"].get("error") and not datasets["^FVX"].get("error"):
        rates_credit["5s10s_bp"] = round((datasets["^TNX"]["end_price"] - datasets["^FVX"]["end_price"]) * 100, 1)
    else:
        rates_credit["5s10s_bp"] = None

    market_calendar = build_market_calendar(session_date, megacaps.keys())
    previous_close = datetime.datetime.combine(previous_session_date, datetime.time(16, 0), tzinfo=NY_TZ)
    catalyst_end = max(
        normalize_market_now(now),
        datetime.datetime.combine(session_date, datetime.time(16, 0), tzinfo=NY_TZ),
    )
    verified_catalysts = build_verified_catalysts(previous_close, catalyst_end)

    data_quality = build_data_quality(
        datasets,
        session_date,
        feed_groups=(market_calendar["feeds"], verified_catalysts["feeds"]),
        local_calendar_symbols=FULL_DAY_CHART_TICKERS,
        previous_session=previous_session_date,
    )

    advances = sum(1 for value in sector_perf.values() if value > 0)
    declines = sum(1 for value in sector_perf.values() if value < 0)
    breadth_share = round((advances / len(sector_perf)) * 100, 1) if sector_perf else 0.0
    context, cards = build_editorial_context(
        datasets, sector_results, megacap_data,
        {**session_charts, **{ticker: entry['session_chart'] for ticker, entry in megacap_data.items()}},
        spy, rsp, session_date,
    )
    editorial, narrative_provenance = generate_editorial(context, cards)
    def observation(card_id):
        return cards.get(card_id, {}).get("observed", "Verified session data unavailable.")

    # Compatibility fields remain plain text in the JSON snapshot.
    sector_bullets = {
        "top_bullet1": observation("sectors"),
        "top_bullet2": observation("breadth"),
        "bot_bullet1": editorial["sector_leadership"]["interpretation"],
        "bot_bullet2": cards.get("sectors", {}).get("watch", "Verified sector data unavailable."),
    }
    mc_descriptions = {ticker: observation("stock_" + ticker) for ticker in megacap_data}
    global_status = {key: observation(key) for key in ("nikkei", "stoxx", "ftse", "hsi")}
    crypto_descriptions = {key: observation(key) for key in ("btc", "eth", "sol", "xrp")}
    daily_takeaway = {
        "what_moved": editorial["investor_takeaway"]["observed"],
        "why": editorial["investor_takeaway"]["interpretation"],
        "what_to_watch": " ".join(editorial["watchlist"]),
    }
    next_session_outlook = {
        "macro": [cards[cid]["watch"] for cid in ("dollar_gold", "oil_equities") if cid in cards],
        "fed_policy": [cards[cid]["watch"] for cid in ("rates", "risk") if cid in cards],
        "earnings_and_catalysts": [cards[cid]["watch"] for cid in ("megacaps", "nasdaq_gap") if cid in cards],
        "risk_factors": editorial["watchlist"][:2],
    }
    snapshot = {
        "report_type": "daily_market_close",
        "session_date": session_date.isoformat(),
        "previous_session_date": previous_session_date.isoformat(),
        "generated_at": normalize_market_now(now).isoformat(),
        "report_mode": narrative_provenance["mode"],
        "narrative_provenance": narrative_provenance,
        "derived_metrics": context["derived_metrics"],
        "data_quality": data_quality,
        "market_calendar": market_calendar,
        "verified_catalysts": verified_catalysts,
        "rates_credit": rates_credit,
        "market_internals": market_internals,
        "asset_catalog": asset_catalog,
        "asset_history": asset_history,
        "market_data": datasets,
        "session_charts": session_charts,
        "mega_cap_data": megacap_data,
        "daily_sector_performance": sector_perf,
        "all_sectors_ranked": all_sectors_ranked,
        "top_sectors": top_sectors,
        "bottom_sectors": bottom_sectors,
        "daily_market_breadth": {
            "advances": advances,
            "declines": declines,
            "positive_sector_share": breadth_share,
            "spy_pct_change": spy["pct_change"] if not spy.get("error") else None,
            "rsp_pct_change": rsp["pct_change"] if not rsp.get("error") else None,
        },
        "narrative": {
            "editorial": editorial,
            "sector_bullets": sector_bullets,
            "megacap_descriptions": mc_descriptions,
            "global_status": global_status,
            "crypto_descriptions": crypto_descriptions,
            "daily_takeaway": daily_takeaway,
            "next_session_outlook": next_session_outlook,
        },
    }

    snapshot_output = Path(snapshot_path)
    archive_dir = Path(archive_root) / session_date.isoformat()
    archive_snapshot_output = archive_dir / "report.json"

    snapshot_output.parent.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    snapshot_json = json.dumps(snapshot, indent=2) + "\n"
    snapshot_output.write_text(snapshot_json, encoding="utf-8")
    archive_snapshot_output.write_text(snapshot_json, encoding="utf-8")
    print(
        f"Successfully generated {snapshot_output} and {archive_snapshot_output} "
        f"for {full_date}"
    )
    return True


if __name__ == "__main__":
    generate_html()
