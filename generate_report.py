import datetime
import html
import json
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
# CLAUDE API HELPERS
# ─────────────────────────────────────────────
def claude(prompt, max_tokens=400, fallback=""):
    if not ANTHROPIC_API_KEY:
        print("  ANTHROPIC_API_KEY not set — using fallback.")
        return fallback
    try:
        payload = json.dumps(
            {
                "model": ANTHROPIC_MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
            text = body["content"][0]["text"].strip()
            print(f"  Claude OK ({len(text)} chars)")
            return text
    except Exception as exc:
        print(f"  Claude API error: {exc} — using fallback.")
        return fallback


def claude_json(prompt, required_keys, max_tokens=600, fallback=None):
    raw = claude(prompt, max_tokens=max_tokens, fallback="")
    if not raw:
        return fallback or {}
    try:
        start_idx = raw.find("{")
        end_idx = raw.rfind("}")
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON object found in response")
        result = json.loads(raw[start_idx : end_idx + 1])
        if not required_keys.issubset(result.keys()):
            raise ValueError(f"Missing keys: {required_keys - result.keys()}")
        return result
    except Exception as exc:
        print(f"  Claude JSON parse error: {exc} — using fallback.")
        return fallback or {}


def should_use_ai():
    return bool(ANTHROPIC_API_KEY)


# ─────────────────────────────────────────────
# NARRATIVE GENERATORS
# ─────────────────────────────────────────────
def build_next_session_outlook_fallback(market_context):
    top1 = market_context["top_sectors"].split(", ")[0]
    bottom1 = market_context["bottom_sectors"].split(", ")[0]
    vix = market_context["vix_close"]
    tnx = market_context["tnx_close"]
    dxy = market_context["dxy_close"]
    return {
        "macro": [
            f"Watch inflation, labor, and consumer data against a {tnx:.2f}% 10-year yield.",
            f"Hot data would pressure duration-sensitive groups; softer data could support {top1}.",
        ],
        "fed_policy": [
            "Track whether Fed speakers validate or resist the current easing in financial conditions.",
            f"Rates and the DXY at {dxy:.2f} remain the main valuation inputs for growth stocks.",
        ],
        "earnings_and_catalysts": [
            f"Guidance must confirm that leadership in {top1} is supported by demand and margins.",
            f"A weak read-through would expose continued underperformance in {bottom1}.",
        ],
        "risk_factors": [
            f"VIX at {vix:.2f} defines the market's current downside cushion.",
            "Watch for a reversal in mega-cap momentum, a yield spike, or abrupt commodity volatility.",
        ],
    }


def generate_next_session_outlook_claude(market_context):
    prompt = (
        "You are a senior equity strategist writing a compact next-session outlook after a completed U.S. market close. "
        "Return four arrays of exactly two short bullets each. Each bullet must be one sentence, "
        "actionable, specific, and grounded in the supplied data. Treat possible drivers as inferences, not proven causes. "
        "Avoid paragraphs and generic language.\n\n"
        f"Completed session: {market_context['session_date']}\n"
        f"S&P 500: {market_context['sp_pct']:+.2f}% 1D\n"
        f"VIX: {market_context['vix_close']:.2f}\n"
        f"10-year yield: {market_context['tnx_close']:.2f}% ({market_context['tnx_pct']:+.2f}% 1D)\n"
        f"DXY: {market_context['dxy_close']:.2f} ({market_context['dxy_pct']:+.2f}% 1D)\n"
        f"Gold: {market_context['gold_pct']:+.2f}% 1D\n"
        f"Crude: {market_context['oil_pct']:+.2f}% 1D\n"
        f"BTC: {market_context['btc_pct']:+.2f}% 1D\n"
        f"Top sectors: {market_context['top_sectors']}\n"
        f"Bottom sectors: {market_context['bottom_sectors']}\n\n"
        "Respond ONLY as JSON with array-valued keys: macro, fed_policy, "
        "earnings_and_catalysts, risk_factors."
    )
    fallback = build_next_session_outlook_fallback(market_context)
    return claude_json(
        prompt,
        required_keys={"macro", "fed_policy", "earnings_and_catalysts", "risk_factors"},
        max_tokens=500,
        fallback=fallback,
    )


def build_daily_takeaway_fallback(context):
    return {
        "what_moved": (
            f"S&P 500 {context['sp_pct']:+.2f}% for the session; "
            f"{context['top_sector']} led while {context['bottom_sector']} lagged."
        ),
        "why": (
            f"Rates at {context['tnx']:.2f}% and VIX at {context['vix']:.2f} "
            "were observed alongside the session's leadership pattern; causality is not established."
        ),
        "what_to_watch": (
            f"Watch whether yields and DXY at {context['dxy']:.2f} stay contained "
            "enough for breadth to improve."
        ),
    }


def generate_daily_takeaway_claude(context):
    prompt = (
        "You are a senior equity strategist summarizing one completed U.S. trading session. "
        "Return exactly three short decision bullets as JSON. Each value must be one sentence and no more than 28 words. "
        "Separate observed moves from inferred explanations and never state an unsupported cause as fact.\n\n"
        f"Completed session: {context['session_date']}\n"
        f"S&P 500: {context['sp_pct']:+.2f}% 1D\n"
        f"Nasdaq: {context['nd_pct']:+.2f}% 1D\n"
        f"DJIA: {context['dj_pct']:+.2f}% 1D\n"
        f"VIX: {context['vix']:.2f}\n"
        f"10-year yield: {context['tnx']:.2f}%\n"
        f"DXY: {context['dxy']:.2f}\n"
        f"Top sector: {context['top_sector']}\n"
        f"Bottom sector: {context['bottom_sector']}\n\n"
        "Respond ONLY with JSON keys what_moved, why, what_to_watch."
    )
    fallback = build_daily_takeaway_fallback(context)
    return claude_json(
        prompt,
        required_keys={"what_moved", "why", "what_to_watch"},
        max_tokens=240,
        fallback=fallback,
    )


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
    ai_enabled = should_use_ai()

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

    all_sectors_str = ", ".join(
        f"{name} {value:+.2f}%" for name, value in sorted_sectors
    )
    sector_prompt = (
        "Write four one-sentence captions for a completed-session sector ranking: two about leaders and two about laggards. "
        "Be specific, cite daily percentages, label explanations as inference, and return only JSON keys top_bullet1, top_bullet2, "
        "bot_bullet1, bot_bullet2.\n"
        f"All sectors: {all_sectors_str}\n"
        f"Top 4: {top_sectors}\nBottom 4: {bottom_sectors}\n"
        f"S&P 500: {sp['pct_change']:+.2f}% 1D; VIX: {vix['end_price']:.2f}."
    )
    sector_fallback = {
        "top_bullet1": f"{top_sectors[0][0]} led the session ranking at {top_sectors[0][1]:+.2f}%.",
        "top_bullet2": f"{top_sectors[1][0]} followed at {top_sectors[1][1]:+.2f}% for the session.",
        "bot_bullet1": f"{bottom_sectors[0][0]} remained in the lower tier at {bottom_sectors[0][1]:+.2f}%.",
        "bot_bullet2": f"{bottom_sectors[-1][0]} ranked last at {bottom_sectors[-1][1]:+.2f}% for the session.",
    }
    sector_bullets = (
        claude_json(
            sector_prompt,
            required_keys={"top_bullet1", "top_bullet2", "bot_bullet1", "bot_bullet2"},
            max_tokens=300,
            fallback=sector_fallback,
        )
        if ai_enabled
        else sector_fallback
    )
    sector_bullets = sanitize_text_map(sector_bullets)

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
    megacap_data = {
        ticker: {
            "name": company,
            "result": fetch_daily_data(ticker, session_date, previous_session_date),
        }
        for ticker, company in megacaps.items()
    }
    mc_lines = "\n".join(
        f"- {ticker} ({entry['name']}): ${entry['result']['end_price']:,.2f}, "
        f"{entry['result']['pct_change']:+.2f}% 1D"
        for ticker, entry in megacap_data.items()
    )
    mc_prompt = (
        "Write one concise analytical sentence per ticker about the completed session. Do not start with the ticker or company name. "
        "Distinguish observed price action from inferred significance. Return only a JSON object mapping each ticker to its sentence.\n"
        f"S&P 500: {sp['pct_change']:+.2f}% 1D; VIX: {vix['end_price']:.2f}; "
        f"10-year: {tnx['end_price']:.2f}%.\n{mc_lines}"
    )
    mc_fallback = {
        ticker: f"Closed at ${entry['result']['end_price']:,.2f} after a {entry['result']['pct_change']:+.2f}% session move."
        for ticker, entry in megacap_data.items()
    }
    mc_descriptions = (
        claude_json(
            mc_prompt,
            required_keys=set(megacap_data.keys()),
            max_tokens=900,
            fallback=mc_fallback,
        )
        if ai_enabled
        else mc_fallback
    )
    mc_descriptions = sanitize_text_map(mc_descriptions)
    logo_slugs = {
        "AAPL": "apple",
        "MSFT": "microsoft",
        "NVDA": "nvidia",
        "AMZN": "amazon",
        "META": "meta-platforms",
        "SNDK": "sandisk",
        "AMD": "advanced-micro-devices",
        "INTC": "intel",
        "MU": "micron-technology",
    }
    megacap_html = "".join(
        render_megacap_row(
            ticker,
            entry["name"],
            entry["result"],
            mc_descriptions[ticker],
            logo_slugs.get(ticker, ""),
        )
        for ticker, entry in megacap_data.items()
    )

    global_prompt = (
        "Write one short observed-status sentence for each index's latest daily close. "
        "Do not claim a cause without supplied evidence. Return only JSON keys nikkei, stoxx, ftse, hsi.\n"
        f"Nikkei: {n225['pct_change']:+.2f}% 1D\n"
        f"Euro Stoxx 50: {stoxx['pct_change']:+.2f}% 1D\n"
        f"FTSE 100: {ftse['pct_change']:+.2f}% 1D\n"
        f"Hang Seng: {hsi['pct_change']:+.2f}% 1D"
    )
    global_fallback = {
        "nikkei": "Japanese equities reflected regional growth and currency positioning.",
        "stoxx": "European blue chips tracked policy and earnings expectations.",
        "ftse": "UK large caps remained sensitive to commodities and sterling.",
        "hsi": "Hong Kong equities traded on China policy and technology sentiment.",
    }
    global_status = (
        claude_json(
            global_prompt,
            required_keys={"nikkei", "stoxx", "ftse", "hsi"},
            max_tokens=300,
            fallback=global_fallback,
        )
        if ai_enabled
        else global_fallback
    )
    global_status = sanitize_text_map(global_status)
    global_rows = "".join(
        (
            render_global_row("Nikkei 225", n225, global_status["nikkei"]),
            render_global_row("Euro Stoxx 50", stoxx, global_status["stoxx"]),
            render_global_row("FTSE 100", ftse, global_status["ftse"]),
            render_global_row("Hang Seng", hsi, global_status["hsi"]),
        )
    )

    crypto_prompt = (
        "Write one short daily-close analytical sentence for BTC, ETH, SOL, and XRP. "
        "Distinguish observations from inference. Return only JSON keys btc, eth, sol, xrp.\n"
        f"BTC {btc['pct_change']:+.2f}% 1D; ETH {eth['pct_change']:+.2f}%; "
        f"SOL {sol['pct_change']:+.2f}%; XRP {xrp['pct_change']:+.2f}%."
    )
    crypto_fallback = {
        "btc": f"Closed at ${btc['end_price']:,.0f} and remained the main crypto risk benchmark.",
        "eth": f"Closed at ${eth['end_price']:,.0f} with relative performance signaling layer-1 risk appetite.",
        "sol": f"Closed at ${sol['end_price']:.2f} as higher-beta crypto exposure moved with liquidity conditions.",
        "xrp": f"Closed at ${xrp['end_price']:.4f} with payments and regulatory headlines still relevant.",
    }
    crypto_descriptions = (
        claude_json(
            crypto_prompt,
            required_keys={"btc", "eth", "sol", "xrp"},
            max_tokens=400,
            fallback=crypto_fallback,
        )
        if ai_enabled
        else crypto_fallback
    )
    crypto_descriptions = sanitize_text_map(crypto_descriptions)

    lookahead_context = {
        "session_date": session_date.isoformat(),
        "sp_pct": sp["pct_change"],
        "vix_close": vix["end_price"],
        "tnx_close": tnx["end_price"],
        "tnx_pct": tnx["pct_change"],
        "dxy_close": dxy["end_price"],
        "dxy_pct": dxy["pct_change"],
        "top_sectors": ", ".join(name for name, _ in top_sectors[:2]),
        "bottom_sectors": ", ".join(name for name, _ in bottom_sectors[:2]),
        "btc_pct": btc["pct_change"],
        "oil_pct": oil["pct_change"],
        "gold_pct": gold["pct_change"],
    }
    next_session_outlook = (
        generate_next_session_outlook_claude(lookahead_context)
        if ai_enabled
        else build_next_session_outlook_fallback(lookahead_context)
    )
    for key in ("macro", "fed_policy", "earnings_and_catalysts", "risk_factors"):
        if not isinstance(next_session_outlook.get(key), list):
            next_session_outlook[key] = [str(next_session_outlook.get(key, ""))]

    takeaway_context = {
        "session_date": session_date.isoformat(),
        "sp_pct": sp["pct_change"],
        "nd_pct": nd["pct_change"],
        "dj_pct": dj["pct_change"],
        "vix": vix["end_price"],
        "tnx": tnx["end_price"],
        "dxy": dxy["end_price"],
        "top_sector": top_sectors[0][0],
        "bottom_sector": bottom_sectors[-1][0],
    }
    daily_takeaway = (
        generate_daily_takeaway_claude(takeaway_context)
        if ai_enabled
        else build_daily_takeaway_fallback(takeaway_context)
    )
    daily_takeaway = sanitize_text_map(daily_takeaway)

    spy = fetch_daily_data("SPY", session_date, previous_session_date)
    rsp = fetch_daily_data("RSP", session_date, previous_session_date)
    advances = sum(1 for value in sector_perf.values() if value > 0)
    declines = sum(1 for value in sector_perf.values() if value < 0)
    breadth_share = round((advances / len(sector_perf)) * 100, 1) if sector_perf else 0.0

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

    market_tone = "Risk-On" if sp["pct_change"] >= 0 else "Risk-Off"
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

    title = f"Daily Market Summary – {full_date}"
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{render_html_text(title)}</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg">
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
        "report_mode": "ai" if ai_enabled else "deterministic_fallback",
        "market_data": datasets,
        "session_charts": session_charts,
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
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(html_content, encoding="utf-8")
    snapshot_output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Successfully generated {snapshot_output} and {report_output} for {full_date}")
    return True


if __name__ == "__main__":
    generate_html()
