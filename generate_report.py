import datetime
import html
import json
import math
import os
import re
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf


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
    "^TNX": (0.1, 20),
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
NY_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE_SETTLE_TIME = datetime.time(16, 15)
SESSION_LOOKBACK_DAYS = 15
PREMIUM_DESIGN_MARKER = "DESIGN TOKENS · Editorial-Finance Premium Minimalist"


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


def fetch_recent_session_dates(candidate_date):
    """Use S&P 500 bars as the source of truth for U.S. trading sessions."""
    history = yf.Ticker("^GSPC").history(
        start=(candidate_date - datetime.timedelta(days=SESSION_LOOKBACK_DAYS)).isoformat(),
        end=(candidate_date + datetime.timedelta(days=1)).isoformat(),
        interval="1d",
    )
    history = history.dropna(subset=["Close"])
    return sorted({index_date(value) for value in history.index if index_date(value) <= candidate_date})


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


def render_html_text(value):
    return html.escape(str(value), quote=True)


def render_html_with_strong(value):
    escaped = render_html_text(value)
    return escaped.replace("&lt;strong&gt;", "<strong>").replace("&lt;/strong&gt;", "</strong>")


def preserve_premium_shell(existing_html, title, body_html):
    """Reuse a checked-in premium design shell while replacing its report body."""
    if PREMIUM_DESIGN_MARKER not in existing_html:
        return None
    style_end = existing_html.find("</style>")
    if style_end == -1:
        return None
    shell = existing_html[: style_end + len("</style>")]
    shell = re.sub(
        r"<title>.*?</title>",
        f"<title>{render_html_text(title)}</title>",
        shell,
        count=1,
        flags=re.DOTALL,
    )
    return f"{shell}\n</head>\n<body>\n{body_html}\n</body>\n</html>\n"


def sanitize_text_map(values, allow_strong=False):
    sanitizer = render_html_with_strong if allow_strong else render_html_text
    return {key: sanitizer(value) for key, value in values.items()}


def sanitize_string_list(values):
    if not isinstance(values, list):
        return []
    return [render_html_text(value) for value in values if str(value).strip()]


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
                "error": None,
            }
        except Exception as exc:
            print(f"  Exception fetching {ticker_used}: {exc}")

    print(f"  All fetch attempts failed for {ticker_symbol}. Using zeroed data.")
    return {
        "dates": [],
        "closes": [],
        "end_price": 0.0,
        "pct_change": 0.0,
        "abs_change": 0.0,
        "prev_close": 0.0,
        "session_open": 0.0,
        "day_high": 0.0,
        "day_low": 0.0,
        "session_date": None,
        "previous_session_date": None,
        "ticker_used": ticker_symbol,
        "error": f"Data unavailable for {ticker_symbol}",
    }


def market_datetime(value):
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime.datetime):
        value = datetime.datetime.fromisoformat(str(value))
    if value.tzinfo is None:
        return value.replace(tzinfo=NY_TZ)
    return value.astimezone(NY_TZ)


def fetch_daily_chart_data(ticker_symbol, session_date, fallback_data=None):
    """Fetch regular-hours intraday points for one completed session."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(
            start=session_date.isoformat(),
            end=(session_date + datetime.timedelta(days=1)).isoformat(),
            interval="5m",
            prepost=False,
        )

        hist = hist.dropna(subset=["Close"])
        regular_positions = []
        regular_times = []
        for position, value in enumerate(hist.index):
            timestamp = market_datetime(value)
            if (
                timestamp.date() == session_date
                and datetime.time(9, 30) <= timestamp.time() <= datetime.time(16, 0)
            ):
                regular_positions.append(position)
                regular_times.append(timestamp)
        if len(regular_positions) < 2:
            raise ValueError("Not enough regular-hours intraday data returned")

        return {
            "times": [timestamp.strftime("%I:%M %p").lstrip("0") for timestamp in regular_times],
            "closes": [round(float(hist["Close"].iloc[position]), 2) for position in regular_positions],
            "source": "intraday_5m",
            "session_date": session_date.isoformat(),
            "error": None,
        }
    except Exception as exc:
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
             'limitations':['No verified news, earnings or economic calendar; do not infer events.',
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


# ─────────────────────────────────────────────
# SVG / HTML HELPERS
# ─────────────────────────────────────────────
def fmt_date(dt, include_day=True):
    if include_day:
        return f"{dt.strftime('%b')} {dt.day}"
    return f"{dt.strftime('%B')} {dt.day}, {dt.strftime('%Y')}"


def sparkline_svg(closes, positive=True, width=180, height=54, css_class="sparkline"):
    values = []
    for value in closes or []:
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue

    if not values:
        return (
            f'<svg class="{css_class} empty" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="Chart data unavailable">'
            f'<line x1="4" y1="{height / 2:.1f}" x2="{width - 4}" y2="{height / 2:.1f}" '
            'class="sparkline-muted"/></svg>'
        )

    if len(values) == 1:
        values = [values[0], values[0]]

    minimum = min(values)
    maximum = max(values)
    value_range = maximum - minimum or 1.0
    pad_x = 4.0
    pad_y = 5.0
    x_step = (width - pad_x * 2) / max(len(values) - 1, 1)
    points = []

    for index, value in enumerate(values):
        x = pad_x + index * x_step
        y = height - pad_y - ((value - minimum) / value_range) * (height - pad_y * 2)
        points.append(f"{x:.2f},{y:.2f}")

    trend_class = "positive" if positive else "negative"
    label = f"Sparkline from {values[0]:,.2f} to {values[-1]:,.2f}"
    return (
        f'<svg class="{css_class} {trend_class}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{render_html_text(label)}" preserveAspectRatio="none">'
        f'<polyline points="{" ".join(points)}" class="sparkline-line"/>'
        "</svg>"
    )


def render_bullet_list(items, css_class="decision-list"):
    safe_items = sanitize_string_list(items)
    return f'<ul class="{css_class}">' + "".join(f"<li>{item}</li>" for item in safe_items) + "</ul>"


def format_metric_value(symbol, data):
    value = data["end_price"]
    if symbol in ("BTC-USD", "ETH-USD"):
        return f"${value:,.0f}"
    if symbol == "^TNX":
        return f"{value:.2f}%"
    if symbol == "^VIX":
        return f"{value:.2f}"
    return f"{value:,.2f}"


def render_metric_tile(name, symbol, data, chart_data):
    pct = data["pct_change"]
    css_class = "positive" if pct >= 0 else "negative"
    arrow = "▲" if pct >= 0 else "▼"
    sign = "+" if pct >= 0 else "−"
    sparkline = sparkline_svg(
        chart_data.get("closes", []),
        positive=pct >= 0,
        width=180,
        height=52,
        css_class="metric-sparkline",
    )
    return (
        '<article class="metric-tile">'
        '<div class="metric-head">'
        f'<span class="metric-name">{render_html_text(name)}</span>'
        f'<span class="metric-change {css_class}">{arrow} {sign}{abs(pct):.2f}%</span>'
        "</div>"
        f'<div class="metric-value">{format_metric_value(symbol, data)}</div>'
        f'<div class="metric-chart">{sparkline}</div>'
        "</article>"
    )


def render_sector_chart(all_sectors_ranked):
    max_abs = max((abs(value) for _, value in all_sectors_ranked), default=1.0) or 1.0
    rows = []
    for rank, (name, value) in enumerate(all_sectors_ranked, start=1):
        css_class = "positive" if value >= 0 else "negative"
        width = max(2.5, abs(value) / max_abs * 100)
        rows.append(
            '<div class="sector-row">'
            f'<div class="sector-rank">{rank:02d}</div>'
            f'<div class="sector-name">{render_html_text(name)}</div>'
            '<div class="sector-track">'
            f'<div class="sector-bar {css_class}" style="width:{width:.2f}%"></div>'
            "</div>"
            f'<div class="sector-value {css_class}">{value:+.2f}%</div>'
            "</div>"
        )
    return '<div class="sector-chart" role="img" aria-label="All eleven sectors ranked by daily return">' + "".join(rows) + "</div>"


def render_megacap_row(ticker, company, data, description, logo_slug):
    pct = data["pct_change"]
    css_class = "positive" if pct >= 0 else "negative"
    sparkline = sparkline_svg(
        data.get("closes", []),
        positive=pct >= 0,
        width=150,
        height=48,
        css_class="row-sparkline",
    )
    logo = (
        f'<img src="https://s3-symbol-logo.tradingview.com/{logo_slug}.svg" '
        f'alt="{ticker} logo" class="company-logo" onerror="this.style.display=\'none\'">'
        if logo_slug
        else ""
    )
    error_note = '<span class="data-error">data error</span>' if data.get("error") else ""
    return (
        f'<article class="company-row" data-ticker="{ticker}">'
        f'<div class="company-id">{logo}<div><strong>{ticker}</strong><span>{render_html_text(company)}</span></div></div>'
        f'<div class="company-note">{description} {error_note}</div>'
        f'<div class="company-spark">{sparkline}</div>'
        '<div class="company-stats">'
        f'<span><small>Close</small>${data["end_price"]:,.2f}</span>'
        f'<span><small>Day High</small>${data["day_high"]:,.2f}</span>'
        f'<span><small>Day Low</small>${data["day_low"]:,.2f}</span>'
        f'<span class="{css_class}"><small>1D</small>{pct:+.2f}%</span>'
        "</div>"
        "</article>"
    )


def render_global_row(name, data, status):
    pct = data["pct_change"]
    css_class = "positive" if pct >= 0 else "negative"
    sparkline = sparkline_svg(
        data.get("closes", []),
        positive=pct >= 0,
        width=120,
        height=34,
        css_class="table-sparkline",
    )
    return (
        "<tr>"
        f'<td class="global-name">{render_html_text(name)}</td>'
        f'<td class="number">{data["end_price"]:,.2f}</td>'
        f'<td class="number {css_class}">{pct:+.2f}%</td>'
        f'<td class="spark-cell">{sparkline}</td>'
        f"<td>{status}</td>"
        "</tr>"
    )


def render_ticker_item(name, value, data):
    pct = data["pct_change"]
    css_class = "positive" if pct >= 0 else "negative"
    return (
        '<div class="ticker-item">'
        f'<span class="ticker-name">{render_html_text(name)}</span>'
        f'<span class="ticker-value">{value}</span>'
        f'<span class="ticker-change {css_class}">{pct:+.2f}% 1D</span>'
        "</div>"
    )


def tradingview_widget_html():
    return r'''
<section class="section tradingview-section" aria-labelledby="tradingview-heading">
  <div class="section-heading compact-heading">
    <div><div class="section-label">Explore Further</div><h2 id="tradingview-heading">Interactive Mega-Cap Charts</h2></div>
    <p>Supplementary TradingView view for deeper timeframes and interaction.</p>
  </div>
  <div class="tradingview-card">
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>
      {
        "lineWidth": 2,
        "lineType": 0,
        "chartType": "area",
        "backgroundColor": "#0F0F0F",
        "widgetFontColor": "#DBDBDB",
        "gridLineColor": "rgba(242,242,242,0.06)",
        "upColor": "#22ab94",
        "downColor": "#f7525f",
        "colorTheme": "dark",
        "isTransparent": false,
        "locale": "en",
        "changeMode": "price-and-percent",
        "symbols": [
          ["NASDAQ:AAPL|1D"], ["NASDAQ:MSFT|1D"], ["NASDAQ:NVDA|1D"],
          ["NASDAQ:AMZN|1D"], ["NASDAQ:META|1D"], ["NASDAQ:SNDK|1D"],
          ["NASDAQ:AMD|1D"], ["NASDAQ:INTC|1D"], ["NASDAQ:MU|1D"]
        ],
        "dateRanges": ["1d|1", "1m|30", "3m|60", "12m|1D", "all|1M"],
        "autosize": true,
        "height": "520"
      }
      </script>
    </div>
  </div>
</section>
'''


# ─────────────────────────────────────────────
# MAIN HTML GENERATOR
# ─────────────────────────────────────────────
def generate_html(now=None, snapshot_path="report_snapshot.json", report_path="public/legacy-report.html"):
    session_date, previous_session_date = resolve_completed_sessions(now)
    if not has_new_session(session_date, snapshot_path):
        print(f"No new completed trading session after {session_date.isoformat()}; leaving artifacts unchanged.")
        return False

    print(f"Fetching market data for completed session {session_date.isoformat()}...")

    ticker_symbols = (
        "^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^TNX", "^IRX", "DX-Y.NYB",
        "GC=F", "CL=F", "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
        "^N225", "^STOXX50E", "^FTSE", "^HSI",
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

    sp = datasets["^GSPC"]
    nd = datasets["^IXIC"]
    dj = datasets["^DJI"]
    rut = datasets["^RUT"]
    vix = datasets["^VIX"]
    tnx = datasets["^TNX"]
    irx = datasets["^IRX"]
    dxy = datasets["DX-Y.NYB"]
    gold = datasets["GC=F"]
    oil = datasets["CL=F"]
    btc = datasets["BTC-USD"]
    eth = datasets["ETH-USD"]
    sol = datasets["SOL-USD"]
    xrp = datasets["XRP-USD"]
    n225 = datasets["^N225"]
    stoxx = datasets["^STOXX50E"]
    ftse = datasets["^FTSE"]
    hsi = datasets["^HSI"]

    session_date_short = fmt_date(session_date)
    previous_session_short = fmt_date(previous_session_date)
    year_str = session_date.strftime("%Y")
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
        symbol: fetch_daily_chart_data(symbol, session_date, fallback_data=datasets[symbol])
        for _, symbol in SUMMARY_TILE_TICKERS
    }
    metric_tiles = "".join(
        render_metric_tile(name, symbol, datasets[symbol], session_charts[symbol])
        for name, symbol in SUMMARY_TILE_TICKERS
    )

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
    advances = sum(1 for value in sector_perf.values() if value > 0)
    declines = sum(1 for value in sector_perf.values() if value < 0)
    breadth_share = round((advances / len(sector_perf)) * 100, 1) if sector_perf else 0.0
    context, cards = build_editorial_context(
        datasets, sector_results, megacap_data,
        {**session_charts, **{ticker: entry['session_chart'] for ticker, entry in megacap_data.items()}},
        spy, rsp, session_date,
    )
    editorial, narrative_provenance = generate_editorial(context, cards)
    ai_enabled = narrative_provenance["mode"] == "ai"

    def observation(card_id):
        return cards.get(card_id, {}).get("observed", "Verified session data unavailable.")

    # Compatibility fields remain plain text; escape only at the HTML boundary.
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
    logo_slugs = {"AAPL": "apple", "MSFT": "microsoft", "NVDA": "nvidia", "AMZN": "amazon",
                  "META": "meta-platforms", "SNDK": "sandisk", "AMD": "advanced-micro-devices",
                  "INTC": "intel", "MU": "micron-technology"}
    megacap_html = "".join(render_megacap_row(ticker, entry["name"], entry["result"],
                         html.escape(mc_descriptions[ticker]), logo_slugs.get(ticker, ""))
                         for ticker, entry in megacap_data.items())
    global_rows = "".join(render_global_row(name, data, html.escape(global_status[key]))
                         for name, data, key in (("Nikkei 225", n225, "nikkei"),
                         ("Euro Stoxx 50", stoxx, "stoxx"), ("FTSE 100", ftse, "ftse"),
                         ("Hang Seng", hsi, "hsi")))

    ticker_items = "".join(
        (
            render_ticker_item("S&P 500", f"{sp['end_price']:,.2f}", sp),
            render_ticker_item("Nasdaq", f"{nd['end_price']:,.2f}", nd),
            render_ticker_item("DJIA", f"{dj['end_price']:,.2f}", dj),
            render_ticker_item("VIX", f"{vix['end_price']:.2f}", vix),
            render_ticker_item("10Y", f"{tnx['end_price']:.2f}%", tnx),
            render_ticker_item("DXY", f"{dxy['end_price']:.2f}", dxy),
            render_ticker_item("BTC", f"${btc['end_price']:,.0f}", btc),
            render_ticker_item("ETH", f"${eth['end_price']:,.0f}", eth),
        )
    )
    ticker_tape = f'<div class="ticker-track">{ticker_items}{ticker_items}</div>'

    market_tone = {"risk_on_confirmed": "Risk-On", "risk_off_confirmed": "Risk-Off"}.get(context["derived_metrics"].get("risk_confirmation", {}).get("signal"), "Mixed")
    tone_class = "positive" if sp["pct_change"] >= 0 else "negative"
    sector_chart = render_sector_chart(all_sectors_ranked)

    crypto_cards = "".join(
        (
            f'<article class="asset-card"><span>Bitcoin</span><strong>${btc["end_price"]:,.0f}</strong><em class="{"positive" if btc["pct_change"] >= 0 else "negative"}">{btc["pct_change"]:+.2f}%</em><p>{crypto_descriptions["btc"]}</p></article>',
            f'<article class="asset-card"><span>Ethereum</span><strong>${eth["end_price"]:,.0f}</strong><em class="{"positive" if eth["pct_change"] >= 0 else "negative"}">{eth["pct_change"]:+.2f}%</em><p>{crypto_descriptions["eth"]}</p></article>',
            f'<article class="asset-card"><span>Solana</span><strong>${sol["end_price"]:,.2f}</strong><em class="{"positive" if sol["pct_change"] >= 0 else "negative"}">{sol["pct_change"]:+.2f}%</em><p>{crypto_descriptions["sol"]}</p></article>',
            f'<article class="asset-card"><span>XRP</span><strong>${xrp["end_price"]:.4f}</strong><em class="{"positive" if xrp["pct_change"] >= 0 else "negative"}">{xrp["pct_change"]:+.2f}%</em><p>{crypto_descriptions["xrp"]}</p></article>',
        )
    )

    next_session_outlook_cards = "".join(
        (
            f'<article class="decision-card"><span>Macro</span>{render_bullet_list(next_session_outlook["macro"])}</article>',
            f'<article class="decision-card"><span>Fed & Rates</span>{render_bullet_list(next_session_outlook["fed_policy"])}</article>',
            f'<article class="decision-card"><span>Earnings & Catalysts</span>{render_bullet_list(next_session_outlook["earnings_and_catalysts"])}</article>',
            f'<article class="decision-card"><span>Risk Dashboard</span>{render_bullet_list(next_session_outlook["risk_factors"])}</article>',
        )
    )

    daily_takeaway_html = (
        '<ul class="takeaway-list">'
        f'<li><span>What moved</span>{daily_takeaway["what_moved"]}</li>'
        f'<li><span>Possible drivers</span>{daily_takeaway["why"]}</li>'
        f'<li><span>What to watch next</span>{daily_takeaway["what_to_watch"]}</li>'
        "</ul>"
    )

    title = f"Stock Market Summary – {full_date} | The Daily Tape"
    canonical_url = f"https://coolxng.github.io/market-summary/reports/{session_date.isoformat()}/"
    description = (
        f"U.S. stock market close summary for {full_date}, including major indexes, "
        "sector breadth, mega-cap leadership, rates, commodities, global markets, and crypto."
    )
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{render_html_text(title)}</title>
<meta name="description" content="{render_html_text(description)}">
<link rel="canonical" href="{canonical_url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="The Daily Tape">
<meta property="og:title" content="{render_html_text(title)}">
<meta property="og:description" content="{render_html_text(description)}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:image" content="https://coolxng.github.io/market-summary/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{render_html_text(title)}">
<meta name="twitter:description" content="{render_html_text(description)}">
<meta name="twitter:image" content="https://coolxng.github.io/market-summary/og.png">
<link rel="icon" type="image/svg+xml" href="https://coolxng.github.io/market-summary/favicon.svg">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<style>
/* {PREMIUM_DESIGN_MARKER} */
:root {{
  --bg:#000000; --surface:#080808; --surface-2:#101010;
  --border:rgba(255,255,255,.10); --border-hover:rgba(255,255,255,.18); --text:rgba(255,255,255,.94); --muted:rgba(255,255,255,.58);
  --green:#30d158; --red:#ff453a; --accent:#0a84ff; --purple:#bf5af2;
  --shadow:none;
}}
* {{ box-sizing:border-box; }}
html {{ background:var(--bg); scroll-behavior:smooth; }}
body {{ margin:0; min-height:100vh; background:var(--bg); color:var(--text); font-family:Inter,system-ui,sans-serif; line-height:1.5; overflow-x:hidden; }}
a {{ color:inherit; text-decoration:none; }}
.positive {{ color:var(--green)!important; }} .negative {{ color:var(--red)!important; }}
.report-shell {{ position:relative; }}
.report-header {{ position:sticky; top:0; z-index:20; background:#000; border-bottom:1px solid var(--border); }}
.header-main {{ max-width:1320px; margin:auto; padding:18px 34px 14px; display:flex; align-items:center; justify-content:space-between; gap:18px; }}
.report-id {{ display:flex; align-items:center; gap:14px; min-width:0; }}
.report-mark {{ width:34px; height:34px; border-radius:10px; display:grid; place-items:center; background:var(--accent); color:#fff; font:700 13px 'Space Grotesk'; }}
.report-title {{ min-width:0; }}
.report-title strong {{ display:block; font:600 17px 'Space Grotesk'; letter-spacing:-.02em; }}
.report-title span {{ display:block; color:var(--muted); font-size:11px; margin-top:2px; }}
.header-meta {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end; }}
.tone-badge,.date-chip {{ padding:6px 10px; border:1px solid var(--border); border-radius:999px; font-size:10px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; background:var(--surface-2); }}
.ticker-window {{ overflow:hidden; border-top:1px solid var(--border); background:#000; }}
.ticker-track {{ display:flex; width:max-content; animation:ticker 55s linear infinite; }}
.ticker-track:hover {{ animation-play-state:paused; }}
@keyframes ticker {{ to {{ transform:translateX(-50%); }} }}
.ticker-item {{ display:grid; grid-template-columns:auto auto; column-gap:10px; padding:10px 24px; border-right:1px solid var(--border); white-space:nowrap; }}
.ticker-name {{ color:var(--muted); font-size:9px; text-transform:uppercase; letter-spacing:.1em; }}
.ticker-value {{ font:600 12px 'Space Grotesk'; }}
.ticker-change {{ grid-column:2; font-size:9px; font-weight:700; }}
.container {{ max-width:1320px; margin:auto; padding:26px 34px 80px; }}
.metric-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-bottom:26px; }}
.metric-tile,.panel,.asset-card,.decision-card,.tradingview-card {{ background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow); }}
.metric-tile:hover,.panel:hover,.asset-card:hover,.decision-card:hover,.tradingview-card:hover,.takeaway-list li:hover {{ background:var(--surface-2); border-color:var(--border-hover); }}
.metric-tile {{ border-radius:12px; padding:14px 15px 10px; min-width:0; }}
.metric-head {{ display:flex; justify-content:space-between; gap:8px; align-items:center; }}
.metric-name {{ color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.11em; font-weight:700; }}
.metric-change {{ font-size:10px; font-weight:700; }}
.metric-value {{ font:700 25px 'Space Grotesk'; letter-spacing:-.04em; margin-top:8px; }}
.metric-chart {{ height:52px; margin-top:5px; }}
.metric-sparkline,.row-sparkline,.table-sparkline {{ width:100%; height:100%; display:block; overflow:visible; }}
.sparkline-line {{ fill:none; stroke:currentColor; stroke-width:2.25; vector-effect:non-scaling-stroke; stroke-linecap:round; stroke-linejoin:round; }}
.sparkline-muted {{ stroke:var(--muted); stroke-width:1; stroke-dasharray:3 4; }}
.section {{ margin-top:44px; padding-top:28px; border-top:1px solid var(--border); }}
.section-heading {{ display:flex; justify-content:space-between; align-items:end; gap:24px; margin-bottom:17px; }}
.section-heading h2 {{ margin:2px 0 0; font:600 clamp(22px,3vw,32px) 'Space Grotesk'; letter-spacing:-.035em; }}
.section-heading p {{ margin:0; color:var(--muted); max-width:560px; font-size:12px; text-align:right; }}
.section-label {{ color:var(--accent); font-size:9px; font-weight:700; letter-spacing:.16em; text-transform:uppercase; }}
.panel {{ border-radius:12px; padding:18px; }}
.breadth-strip {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:12px; }}
.breadth-stat {{ border:1px solid var(--border); border-radius:12px; padding:12px; background:var(--surface-2); }}
.breadth-stat span {{ color:var(--muted); font-size:9px; text-transform:uppercase; letter-spacing:.1em; }}
.breadth-stat strong {{ display:block; font:700 20px 'Space Grotesk'; margin-top:3px; }}
.sector-chart {{ display:flex; flex-direction:column; gap:9px; }}
.sector-row {{ display:grid; grid-template-columns:28px minmax(150px,220px) minmax(120px,1fr) 70px; gap:10px; align-items:center; }}
.sector-rank {{ color:var(--muted); font:600 10px 'Space Grotesk'; }}
.sector-name {{ font-size:11px; font-weight:600; }}
.sector-track {{ height:9px; border-radius:999px; background:rgba(255,255,255,.05); overflow:hidden; }}
.sector-bar {{ height:100%; border-radius:999px; background:currentColor; opacity:.9; }}
.sector-value {{ font:700 11px 'Space Grotesk'; text-align:right; }}
.caption-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:14px; }}
.caption-grid p {{ margin:0; padding:10px 12px; background:var(--surface-2); border:1px solid var(--border); border-radius:10px; color:var(--muted); font-size:11px; }}
.company-list {{ overflow:hidden; padding:0; }}
.company-row {{ display:grid; grid-template-columns:150px minmax(220px,1fr) 150px 260px; gap:16px; align-items:center; padding:15px 18px; border-bottom:1px solid var(--border); }}
.company-row:last-child {{ border-bottom:0; }}
.company-id {{ display:flex; align-items:center; gap:10px; }}
.company-logo {{ width:32px; height:32px; border-radius:50%; padding:4px; background:rgba(255,255,255,.08); }}
.company-id strong {{ display:block; font:700 12px 'Space Grotesk'; }}
.company-id span {{ display:block; color:var(--muted); font-size:9px; margin-top:2px; }}
.company-note {{ color:var(--muted); font-size:11px; }}
.company-spark {{ height:48px; }}
.company-stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }}
.company-stats span {{ font:600 10px 'Space Grotesk'; white-space:nowrap; }}
.company-stats small {{ display:block; color:var(--muted); font:700 8px Inter; text-transform:uppercase; letter-spacing:.08em; margin-bottom:3px; }}
.data-error {{ color:var(--red); font-size:9px; }}
.table-wrap {{ overflow:auto; padding:0; }}
table {{ width:100%; border-collapse:collapse; min-width:880px; }}
th {{ color:var(--muted); background:var(--surface-2); text-align:left; font-size:9px; letter-spacing:.1em; text-transform:uppercase; }}
th,td {{ padding:12px 14px; border-bottom:1px solid var(--border); vertical-align:middle; }}
tr:last-child td {{ border-bottom:0; }}
td {{ color:var(--muted); font-size:11px; }}
.global-name {{ color:var(--text); font-weight:700; }}
.number {{ color:var(--text); font:600 11px 'Space Grotesk'; white-space:nowrap; }}
.spark-cell {{ width:140px; height:45px; }}
.asset-grid,.decision-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }}
.asset-card,.decision-card {{ border-radius:12px; padding:15px; }}
.asset-card span,.decision-card>span {{ color:var(--muted); font-size:9px; text-transform:uppercase; letter-spacing:.11em; font-weight:700; }}
.asset-card strong {{ display:block; font:700 22px 'Space Grotesk'; margin-top:7px; }}
.asset-card em {{ display:block; font-style:normal; font-size:10px; font-weight:700; margin-top:3px; }}
.asset-card p {{ color:var(--muted); font-size:10px; margin:10px 0 0; }}
.takeaway-list,.decision-list {{ list-style:none; padding:0; margin:0; }}
.takeaway-list {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }}
.takeaway-list li {{ border:1px solid var(--border); background:var(--surface); border-radius:14px; padding:15px; color:var(--text); font-size:11px; }}
.takeaway-list span {{ display:block; color:var(--accent); font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:.1em; margin-bottom:7px; }}
.decision-list {{ margin-top:10px; display:flex; flex-direction:column; gap:8px; }}
.decision-list li {{ color:var(--muted); font-size:10px; padding-left:13px; position:relative; }}
.decision-list li:before {{ content:'•'; position:absolute; left:0; color:var(--accent); }}
.compact-heading {{ align-items:center; }}
.tradingview-card {{ border-radius:12px; overflow:hidden; height:520px; }}
.tradingview-widget-container,.tradingview-widget-container__widget,.tradingview-card iframe {{ width:100%!important; height:100%!important; }}
.footer {{ max-width:1320px; margin:auto; padding:30px 34px 46px; color:var(--muted); font-size:10px; display:flex; justify-content:space-between; gap:18px; border-top:1px solid var(--border); }}
@media(max-width:1100px) {{
  .metric-grid {{ grid-template-columns:repeat(2,1fr); }}
  .company-row {{ grid-template-columns:135px 1fr 130px; }}
  .company-stats {{ grid-column:2 / 4; }}
  .asset-grid,.decision-grid {{ grid-template-columns:repeat(2,1fr); }}
}}
@media(max-width:720px) {{
  .header-main,.container,.footer {{ padding-left:16px; padding-right:16px; }}
  .header-main,.section-heading {{ align-items:flex-start; }}
  .header-main,.section-heading,.footer {{ flex-direction:column; }}
  .header-meta {{ justify-content:flex-start; }}
  .section-heading p {{ text-align:left; }}
  .metric-grid,.breadth-strip,.caption-grid,.asset-grid,.decision-grid,.takeaway-list {{ grid-template-columns:1fr; }}
  .sector-row {{ grid-template-columns:24px 130px 1fr 62px; gap:7px; }}
  .company-row {{ grid-template-columns:1fr 110px; }}
  .company-note,.company-stats {{ grid-column:1 / 3; }}
}}
@media(prefers-reduced-motion:reduce) {{ .ticker-track {{ animation:none; }} }}
</style>
</head>
<body>
<div class="report-shell">
<header class="report-header">
  <div class="header-main">
    <div class="report-id">
      <div class="report-mark">MS</div>
      <div class="report-title"><strong>Daily Market Close</strong><span>{session_date_short}, {year_str} · Versus {previous_session_short} close</span></div>
    </div>
    <div class="header-meta"><span class="tone-badge {tone_class}">{market_tone}</span><span class="date-chip">Post-Market Close</span></div>
  </div>
  <div class="ticker-window" aria-label="Scrolling market ticker">{ticker_tape}</div>
</header>

<main class="container">
  <section aria-label="Core market metrics"><div class="metric-grid">{metric_tiles}</div></section>

  <section class="section" id="sectors">
    <div class="section-heading"><div><div class="section-label">01 · Breadth & Sectors</div><h2>All 11 sectors, ranked</h2></div><p>{advances} sectors advanced and {declines} declined. Full ranking replaces prose-first sector coverage.</p></div>
    <div class="breadth-strip">
      <div class="breadth-stat"><span>Cap-Weighted S&P</span><strong>{sp['pct_change']:+.2f}%</strong></div>
      <div class="breadth-stat"><span>Equal-Weight S&P</span><strong>{rsp['pct_change']:+.2f}%</strong></div>
      <div class="breadth-stat"><span>SPY Check</span><strong>{spy['pct_change']:+.2f}%</strong></div>
      <div class="breadth-stat"><span>Positive Sectors</span><strong>{breadth_share:.1f}%</strong></div>
    </div>
    <div class="panel">{sector_chart}<div class="caption-grid"><p>{sector_bullets['top_bullet1']}</p><p>{sector_bullets['top_bullet2']}</p><p>{sector_bullets['bot_bullet1']}</p><p>{sector_bullets['bot_bullet2']}</p></div></div>
  </section>

  <section class="section" id="megacaps">
    <div class="section-heading"><div><div class="section-label">02 · Mega-Cap & AI</div><h2>Session price action</h2></div><p>Each row shows the completed session close, high, low, and 1D move.</p></div>
    <div class="panel company-list">{megacap_html}</div>
  </section>

{tradingview_widget_html()}

  <section class="section" id="global">
    <div class="section-heading"><div><div class="section-label">03 · Global Markets</div><h2>Cross-market read-through</h2></div><p>Latest daily closes provide context around the completed U.S. session.</p></div>
    <div class="panel table-wrap"><table><thead><tr><th>Index</th><th>Close</th><th>1D</th><th>Session Trend</th><th>Status</th></tr></thead><tbody>{global_rows}</tbody></table></div>
  </section>

  <section class="section" id="crypto">
    <div class="section-heading"><div><div class="section-label">04 · Digital Assets</div><h2>Crypto risk dashboard</h2></div><p>Compact price and narrative cards for the broader liquidity read.</p></div>
    <div class="asset-grid">{crypto_cards}</div>
  </section>

  <section class="section" aria-label="Editorial brief">
    <div class="section-heading"><div><h2>{html.escape(editorial['headline'])}</h2></div></div>
    <p>{html.escape(editorial['opening_summary'])}</p>
    <p><strong>Interpretation:</strong> {html.escape(editorial['regime']['interpretation'])}</p>
    <p>{html.escape(editorial['macro_read']['observed'])}</p>
  </section>
  <section class="section" id="takeaway">
    <div class="section-heading"><div><div class="section-label">05 · Decision Summary</div><h2>Investor takeaway</h2></div><p>Three decisions, not another paragraph.</p></div>
    {daily_takeaway_html}
  </section>

  <section class="section" id="outlook">
    <div class="section-heading"><div><div class="section-label">06 · Next Session Outlook</div><h2>What to watch next</h2></div><p>Each category is reduced to two scannable, evidence-aware bullets.</p></div>
    <div class="decision-grid">{next_session_outlook_cards}</div>
  </section>

  <section class="section" id="macro">
    <div class="section-heading"><div><div class="section-label">07 · Macro Reference</div><h2>Rates, dollar, and commodities</h2></div><p>Secondary values retained below the primary digest.</p></div>
    <div class="breadth-strip">
      <div class="breadth-stat"><span>13W T-Bill</span><strong>{irx['end_price']:.2f}%</strong></div>
      <div class="breadth-stat"><span>Gold</span><strong>${gold['end_price']:,.2f}</strong></div>
      <div class="breadth-stat"><span>Crude Oil</span><strong>${oil['end_price']:,.2f}</strong></div>
      <div class="breadth-stat"><span>Russell 2000</span><strong>{rut['end_price']:,.2f}</strong></div>
    </div>
  </section>
</main>

<footer class="footer"><span>Automated Daily Market Summary · Completed U.S. session · Data via yfinance</span><span>Narrative mode: {'Claude' if ai_enabled else 'Deterministic fallback'} · {full_date}</span></footer>
</div>
</body>
</html>
'''

    snapshot = {
        "report_type": "daily_market_close",
        "session_date": session_date.isoformat(),
        "previous_session_date": previous_session_date.isoformat(),
        "generated_at": normalize_market_now(now).isoformat(),
        "report_mode": narrative_provenance["mode"],
        "narrative_provenance": narrative_provenance,
        "derived_metrics": context["derived_metrics"],
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

    report_output = Path(report_path)
    snapshot_output = Path(snapshot_path)
    archive_dir = report_output.parent / "reports" / session_date.isoformat()
    archive_report_output = archive_dir / "index.html"
    archive_snapshot_output = archive_dir / "report.json"

    report_output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_output.parent.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    snapshot_json = json.dumps(snapshot, indent=2) + "\n"
    report_output.write_text(html_content, encoding="utf-8")
    snapshot_output.write_text(snapshot_json, encoding="utf-8")
    archive_report_output.write_text(html_content, encoding="utf-8")
    archive_snapshot_output.write_text(snapshot_json, encoding="utf-8")
    print(
        f"Successfully generated {snapshot_output}, {report_output}, "
        f"{archive_snapshot_output}, and {archive_report_output} for {full_date}"
    )
    return True


if __name__ == "__main__":
    generate_html()
