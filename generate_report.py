import datetime
import html
import json
import os
import urllib.request
from zoneinfo import ZoneInfo

import yfinance as yf

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL   = "claude-sonnet-4-6"

SANITY_BOUNDS = {
    "GC=F":      (1000, 8000),
    "CL=F":      (20,   200),
    "BTC-USD":   (1000, 500000),
    "ETH-USD":   (50,   50000),
    "SOL-USD":   (1,    10000),
    "XRP-USD":   (0.01, 100),
    "^GSPC":     (1000, 20000),
    "^IXIC":     (1000, 50000),
    "^DJI":      (5000, 200000),
    "^RUT":      (500,  10000),
    "^VIX":      (5,    150),
    "^TNX":      (0.1,  20),
    "^IRX":      (0.0,  20),
    "DX-Y.NYB":  (50,   200),
    "^N225":     (10000, 60000),
    "^STOXX50E": (2000,  7000),
    "^FTSE":     (4000,  15000),
    "^HSI":      (10000, 50000),
}

FALLBACKS = {
    "GC=F": "GLD",
    "CL=F": "USO",
}

CORE_TICKERS = ("^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^TNX", "DX-Y.NYB")
NY_TZ = ZoneInfo("America/New_York")

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


def compute_week_window(now=None):
    now = now or current_market_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=NY_TZ)
    weekday = now.weekday()
    days_since_friday = (weekday - 4) % 7
    end_date = now.date() - datetime.timedelta(days=days_since_friday)
    start_date = end_date - datetime.timedelta(days=7)
    return start_date, end_date


def format_display_range(end_date):
    start_date = end_date - datetime.timedelta(days=4)
    return start_date, end_date


def render_html_text(value):
    return html.escape(str(value), quote=True)


def render_html_with_strong(value):
    escaped = render_html_text(value)
    escaped = escaped.replace("&lt;strong&gt;", "<strong>")
    escaped = escaped.replace("&lt;/strong&gt;", "</strong>")
    return escaped


def sanitize_text_map(values, allow_strong=False):
    sanitizer = render_html_with_strong if allow_strong else render_html_text
    return {key: sanitizer(value) for key, value in values.items()}


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


def validate_core_datasets(dataset_map):
    for ticker in CORE_TICKERS:
        validate_dataset(dataset_map[ticker], ticker)

def fetch_weekly_data(ticker_symbol, start_date=None, end_date=None):
    tickers_to_try = [ticker_symbol]
    if ticker_symbol in FALLBACKS:
        tickers_to_try.append(FALLBACKS[ticker_symbol])
    for tk in tickers_to_try:
        try:
            ticker = yf.Ticker(tk)
            if start_date and end_date:
                history_end = end_date + datetime.timedelta(days=1)
                hist = ticker.history(start=start_date.isoformat(), end=history_end.isoformat(), interval="1d")
            else:
                hist = ticker.history(period="10d")
            hist = hist.dropna(subset=["Close"])
            if len(hist) < 2:
                continue
            prev_close = float(hist['Close'].iloc[0])
            chart_hist = hist.iloc[1:] if len(hist) > 2 else hist.iloc[-1:]
            dates      = [d.strftime('%a %m/%d') for d in chart_hist.index]
            closes     = [round(float(v), 2) for v in chart_hist['Close'].tolist()]
            highs      = [round(float(v), 2) for v in chart_hist['High'].tolist()]
            lows       = [round(float(v), 2) for v in chart_hist['Low'].tolist()]
            end_price  = closes[-1]
            if not is_sane(tk, end_price):
                print(f"  Sanity check FAILED for {tk}: end_price={end_price} — trying fallback")
                continue
            pct_change = ((end_price - prev_close) / prev_close) * 100 if prev_close != 0 else 0.0
            abs_change = end_price - prev_close
            week_high  = max(highs) if highs else end_price
            week_low   = min(lows) if lows else end_price
            return {
                "dates": dates, "closes": closes, "end_price": end_price,
                "pct_change": round(pct_change, 2), "abs_change": round(abs_change, 2),
                "prev_close": round(prev_close, 2),
                "week_high": week_high, "week_low": week_low,
                "ticker_used": tk, "error": None,
            }
        except Exception as e:
            print(f"  Exception fetching {tk}: {e}")
            continue
    print(f"  All fetch attempts failed for {ticker_symbol}. Using zeroed data.")
    return {"dates": [], "closes": [], "end_price": 0.0, "pct_change": 0.0,
            "abs_change": 0.0, "prev_close": 0.0, "week_high": 0.0, "week_low": 0.0,
            "ticker_used": ticker_symbol, "error": f"Data unavailable for {ticker_symbol}"}

def fetch_weekly_chart_data(ticker_symbol, start_date=None, end_date=None):
    """Fetch hourly price points for the chart while keeping daily data for summary stats."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        if start_date and end_date:
            history_end = end_date + datetime.timedelta(days=1)
            hist = ticker.history(start=start_date.isoformat(), end=history_end.isoformat(), interval="1h")
        else:
            hist = ticker.history(period="5d", interval="1h")
        if len(hist) < 2:
            raise ValueError("Not enough hourly data returned")
        hist = hist.dropna(subset=["Close"])
        dates = [d.strftime('%a %m/%d %I:%M %p') for d in hist.index]
        closes = [round(float(v), 2) for v in hist['Close'].tolist()]
        return {"dates": dates, "closes": closes, "error": None}
    except Exception as e:
        print(f"  Exception fetching hourly chart data for {ticker_symbol}: {e} — using daily chart fallback")
        fallback = fetch_weekly_data(ticker_symbol, start_date=start_date, end_date=end_date)
        return {"dates": fallback["dates"], "closes": fallback["closes"], "error": fallback.get("error")}

# ─────────────────────────────────────────────
# CLAUDE API HELPERS
# ─────────────────────────────────────────────
def claude(prompt, max_tokens=400, fallback=""):
    if not ANTHROPIC_API_KEY:
        print("  ANTHROPIC_API_KEY not set — using fallback.")
        return fallback
    try:
        payload = json.dumps({
            "model": ANTHROPIC_MODEL, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            ANTHROPIC_API_URL, data=payload,
            headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            text = body["content"][0]["text"].strip()
            print(f"  Claude OK ({len(text)} chars)")
            return text
    except Exception as e:
        print(f"  Claude API error: {e} — using fallback.")
        return fallback

def claude_json(prompt, required_keys, max_tokens=600, fallback=None):
    raw = claude(prompt, max_tokens=max_tokens, fallback="")
    if not raw:
        return fallback or {}
    try:
        start_idx = raw.find('{')
        end_idx   = raw.rfind('}')
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON object found in response")
        result = json.loads(raw[start_idx:end_idx + 1])
        if not required_keys.issubset(result.keys()):
            raise ValueError(f"Missing keys: {required_keys - result.keys()}")
        return result
    except Exception as e:
        print(f"  Claude JSON parse error: {e} — using fallback.")
        return fallback or {}


def should_use_ai():
    return bool(ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────
# CLAUDE-POWERED SECTION GENERATORS
# ─────────────────────────────────────────────
def generate_lookahead_claude(market_context):
    sp_pct   = market_context["sp_pct"]
    vix      = market_context["vix_close"]
    tnx      = market_context["tnx_close"]
    tnx_pct  = market_context["tnx_pct"]
    dxy      = market_context["dxy_close"]
    dxy_pct  = market_context["dxy_pct"]
    top1     = market_context["top_sectors"].split(", ")[0]
    bot1     = market_context["bottom_sectors"].split(", ")[0]
    btc_pct  = market_context["btc_pct"]
    oil_pct  = market_context["oil_pct"]
    gold_pct = market_context["gold_pct"]

    prompt = (
        "You are a senior equity strategist writing the Looking Ahead section of a weekly market summary. "
        "Write four concise, actionable paragraphs (2 sentences each) for next week. Be specific, analytical, "
        "and grounded in the data below — avoid generic phrases. Include what investors should watch, why it matters, "
        "and the likely market implication. Reference actual numbers where relevant.\n\n"
        f"This week: S&P 500 {'+' if sp_pct >= 0 else ''}{sp_pct}% WTD, "
        f"VIX {vix:.2f}, 10-yr yield {tnx:.2f}% ({'+' if tnx_pct >= 0 else ''}{tnx_pct}% WTD), "
        f"DXY {dxy:.2f} ({'+' if dxy_pct >= 0 else ''}{dxy_pct}% WTD), "
        f"Gold {'+' if gold_pct >= 0 else ''}{gold_pct}% WTD, "
        f"Crude {'+' if oil_pct >= 0 else ''}{oil_pct}% WTD, "
        f"BTC {'+' if btc_pct >= 0 else ''}{btc_pct}% WTD. "
        f"Top sectors: {market_context['top_sectors']}. "
        f"Bottom sectors: {market_context['bottom_sectors']}.\n\n"
        "Respond ONLY with a JSON object with these exact keys: macro, fed_policy, earnings_and_catalysts, risk_factors. "
        "No markdown, no preamble."
    )
    fallback = build_lookahead_fallback(market_context)
    result = claude_json(
        prompt,
        required_keys={"macro", "fed_policy", "earnings_and_catalysts", "risk_factors"},
        max_tokens=600, fallback=fallback,
    )
    print("  Section 08 generated via Claude.")
    return result


def build_lookahead_fallback(market_context):
    vix = market_context["vix_close"]
    tnx = market_context["tnx_close"]
    tnx_pct = market_context["tnx_pct"]
    dxy = market_context["dxy_close"]
    top1 = market_context["top_sectors"].split(", ")[0]
    bot1 = market_context["bottom_sectors"].split(", ")[0]
    return {
        "macro": (
            f"Next week's macro tape should be judged through the rates channel: with the 10-year yield at {tnx:.2f}%, "
            f"inflation, jobs, and consumer data need to confirm that growth is cooling without breaking. A hotter print "
            f"would likely pressure duration-sensitive groups such as {bot1}, while a benign release could extend the bid "
            f"in leadership sectors."
        ),
        "fed_policy": (
            f"Fed communication is the key valuation swing factor after the 10-year yield moved {'higher' if tnx_pct >= 0 else 'lower'} "
            f"by {abs(tnx_pct):.2f}% this week. Investors should watch whether officials validate easier financial conditions or push back "
            f"against them; the answer will shape multiples for growth and AI-linked equities."
        ),
        "earnings_and_catalysts": (
            f"Earnings follow-through matters because {top1} is carrying market leadership while {bot1} is lagging. Guidance on AI spending, "
            f"margins, and enterprise demand will determine whether the rally broadens or remains concentrated in a narrow set of winners."
        ),
        "risk_factors": (
            ("The VIX at " + f"{vix:.2f}" + " signals that investors are still paying up for downside protection."
             if vix >= 20 else "The VIX at " + f"{vix:.2f}" + " leaves little cushion for disappointment.")
            + f" Watch for a reversal in mega-cap momentum, a sharp move in yields or the dollar, or commodity volatility that could "
              "quickly turn a constructive tape into a profit-taking event."
        ),
    }

# ─────────────────────────────────────────────
# FORMATTING HELPERS
# ─────────────────────────────────────────────
def fmt_date(dt, include_day=True):
    if include_day:
        return f"{dt.strftime('%b')} {dt.day}"
    return f"{dt.strftime('%B')} {dt.day}, {dt.strftime('%Y')}"

def fmt_chg(pct, abs_val=None, is_yield=False, is_points=False):
    sign  = "+" if pct >= 0 else ""
    color = "pos" if pct >= 0 else "neg"
    arrow = "\u25b2" if pct >= 0 else "\u25bc"
    if is_yield and abs_val is not None:
        bps = round(abs(abs_val) * 100)
        return f'<div class="t-chg {color}">{arrow} {bps} bps WTD</div>'
    elif is_points and abs_val is not None:
        return f'<div class="t-chg {color}">{arrow} {sign}{int(abs(abs_val)):,} pts WTD</div>'
    else:
        return f'<div class="t-chg {color}">{arrow} {sign}{pct}% WTD</div>'

def get_t_item(name, val, pct, is_yield=False, abs_val=None, is_points=False):
    return (
        f'<div class="t-item">'
        f'<div class="t-name">{name}</div>'
        f'<div class="t-val">{val}</div>'
        f'{fmt_chg(pct, abs_val=abs_val, is_yield=is_yield, is_points=is_points)}'
        f'</div>'
    )

# ─────────────────────────────────────────────
# MAIN HTML GENERATOR
# ─────────────────────────────────────────────
def generate_html():
    print("Fetching market data...")
    previous_week_end, week_end = compute_week_window()
    report_start, report_end = format_display_range(week_end)
    ai_enabled = should_use_ai()
    if ai_enabled:
        print("AI mode enabled.")
    else:
        print("AI mode disabled; using deterministic fallback copy for all narrative sections.")

    sp   = fetch_weekly_data("^GSPC", start_date=previous_week_end, end_date=week_end)
    nd   = fetch_weekly_data("^IXIC", start_date=previous_week_end, end_date=week_end)
    dj   = fetch_weekly_data("^DJI", start_date=previous_week_end, end_date=week_end)
    rut  = fetch_weekly_data("^RUT", start_date=previous_week_end, end_date=week_end)
    vix  = fetch_weekly_data("^VIX", start_date=previous_week_end, end_date=week_end)
    tnx  = fetch_weekly_data("^TNX", start_date=previous_week_end, end_date=week_end)
    irx  = fetch_weekly_data("^IRX", start_date=previous_week_end, end_date=week_end)
    dxy  = fetch_weekly_data("DX-Y.NYB", start_date=previous_week_end, end_date=week_end)
    gold = fetch_weekly_data("GC=F", start_date=previous_week_end, end_date=week_end)
    oil  = fetch_weekly_data("CL=F", start_date=previous_week_end, end_date=week_end)
    btc  = fetch_weekly_data("BTC-USD", start_date=previous_week_end, end_date=week_end)
    eth  = fetch_weekly_data("ETH-USD", start_date=previous_week_end, end_date=week_end)
    sol  = fetch_weekly_data("SOL-USD", start_date=previous_week_end, end_date=week_end)
    xrp  = fetch_weekly_data("XRP-USD", start_date=previous_week_end, end_date=week_end)
    n225 = fetch_weekly_data("^N225", start_date=previous_week_end, end_date=week_end)
    stoxx= fetch_weekly_data("^STOXX50E", start_date=previous_week_end, end_date=week_end)
    ftse = fetch_weekly_data("^FTSE", start_date=previous_week_end, end_date=week_end)
    hsi  = fetch_weekly_data("^HSI", start_date=previous_week_end, end_date=week_end)

    datasets = {
        "^GSPC": sp, "^IXIC": nd, "^DJI": dj, "^RUT": rut, "^VIX": vix, "^TNX": tnx, "^IRX": irx,
        "DX-Y.NYB": dxy, "GC=F": gold, "CL=F": oil, "BTC-USD": btc, "ETH-USD": eth,
        "SOL-USD": sol, "XRP-USD": xrp, "^N225": n225, "^STOXX50E": stoxx, "^FTSE": ftse, "^HSI": hsi,
    }
    validate_core_datasets(datasets)

    week_start_str = fmt_date(report_start)
    today_str = fmt_date(report_end)
    year_str = report_end.strftime('%Y')
    full_date = fmt_date(datetime.datetime.combine(report_end, datetime.time(), tzinfo=NY_TZ), include_day=False)
    week_end_date = full_date

    sectors = {
        "Technology (XLK)": "XLK", "Financials (XLF)": "XLF",
        "Energy (XLE)": "XLE", "Healthcare (XLV)": "XLV",
        "Industrials (XLI)": "XLI", "Cons. Discretionary (XLY)": "XLY",
        "Cons. Staples (XLP)": "XLP", "Real Estate (XLRE)": "XLRE",
        "Utilities (XLU)": "XLU", "Materials (XLB)": "XLB",
        "Comm. Services (XLC)": "XLC",
    }
    sector_results = {name: fetch_weekly_data(ticker, start_date=previous_week_end, end_date=week_end) for name, ticker in sectors.items()}
    sector_perf   = {name: result["pct_change"] for name, result in sector_results.items() if not result.get("error")}
    sorted_sectors= sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_sectors) < 4:
        raise ValueError("Insufficient sector data to build the weekly report.")
    top_sectors   = sorted_sectors[:4]
    bottom_sectors= sorted_sectors[-4:]

    sp_pct    = sp["pct_change"]
    vix_close = vix["end_price"]
    tnx_pct   = tnx["pct_change"]

    # Claude: sector bullets
    print("Generating sector analysis via Claude...")
    all_sectors_str = ", ".join(f"{s[0]} {'+' if s[1] >= 0 else ''}{s[1]}%" for s in sorted_sectors)
    sector_prompt = (
        "You are writing bullet point copy for a weekly institutional equity market summary. "
        "Write exactly two sentences for the top performing sectors and two for the bottom sectors. "
        "Each sentence must be distinct and specific to the actual sector named — do not use generic phrasing. "
        "Reference the actual performance percentages. "
        "Respond ONLY with JSON with keys top_bullet1, top_bullet2, bot_bullet1, bot_bullet2. No markdown.\n"
        f"All sectors this week: {all_sectors_str}\n"
        f"Top 4: {', '.join(f'{s[0]} {chr(43) if s[1] >= 0 else str(s[1])}%' for s in top_sectors)}\n"
        f"Bottom 4: {', '.join(f'{s[0]} {chr(43) if s[1] >= 0 else str(s[1])}%' for s in bottom_sectors)}\n"
        f"S&P 500 WTD: {sp_pct}%, VIX: {vix_close:.2f}, 10-yr yield: {tnx['end_price']:.2f}%"
    )
    sector_fallback = {
        "top_bullet1": f"Capital rotated strongly into <strong>{top_sectors[0][0]}</strong>, making it the top performing segment of the S&amp;P 500 this week.",
        "top_bullet2": f"{top_sectors[1][0]} also exhibited strong relative momentum, capturing positive institutional inflows.",
        "bot_bullet1": f"<strong>{bottom_sectors[0][0]}</strong> lagged the broader market, absorbing the heaviest selling pressure over the 5-day period.",
        "bot_bullet2": f"{bottom_sectors[1][0]} also faced structural headwinds, underperforming relative to the core index benchmarks.",
    }
    sector_bullets = (
        claude_json(sector_prompt, required_keys={"top_bullet1","top_bullet2","bot_bullet1","bot_bullet2"}, max_tokens=300, fallback=sector_fallback)
        if ai_enabled else sector_fallback
    )
    sector_bullets = sanitize_text_map(sector_bullets, allow_strong=True)

    # Claude: mega-cap descriptions
    print("Generating mega-cap descriptions via Claude...")
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
    megacap_data = {tk: {"name": name, "result": fetch_weekly_data(tk, start_date=previous_week_end, end_date=week_end)} for tk, name in megacaps.items()}
    mc_lines = "\n".join(
        f"- {tk} ({v['name']}) closed at ${v['result']['end_price']:,.2f}, "
        f"{'+' if v['result']['pct_change'] >= 0 else ''}{v['result']['pct_change']}% WTD"
        for tk, v in megacap_data.items()
    )
    mc_prompt = (
        "You are writing copy for a weekly institutional equity market summary. "
        "Write one sentence per ticker describing its weekly performance and what it signals for the broader market or its sector. "
        "Each sentence must be distinct — do not reuse phrasing. "
        "IMPORTANT: Do NOT start the sentence with the company name or ticker — the name is already displayed separately. "
        "Start with the action or insight directly. Be specific and analytical. Reference the actual closing price and move. "
        "Respond ONLY with a JSON object mapping ticker symbol to sentence string. No markdown.\n"
        f"Market context: S&P 500 {'+' if sp_pct >= 0 else ''}{sp_pct}% WTD, VIX at {vix_close:.2f}, 10-yr yield {tnx['end_price']:.2f}%.\n"
        f"Tickers:\n{mc_lines}"
    )
    mc_fallback = {
        tk: f"Closed the week at ${v['result']['end_price']:,.2f}, posting a {'+' if v['result']['pct_change'] >= 0 else ''}{v['result']['pct_change']}% move."
        for tk, v in megacap_data.items()
    }
    mc_descriptions = claude_json(mc_prompt, required_keys=set(megacap_data.keys()), max_tokens=900, fallback=mc_fallback) if ai_enabled else mc_fallback
    mc_descriptions = sanitize_text_map(mc_descriptions)

    # TradingView stock logos
    # Pattern: https://s3-symbol-logo.tradingview.com/{slug}.svg
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
    megacap_html = ""
    rendered_megacaps = set()
    for tk, v in megacap_data.items():
        if tk in rendered_megacaps:
            continue
        rendered_megacaps.add(tk)
        r       = v["result"]
        c_pct   = r["pct_change"]
        c_abs   = r["abs_change"]
        c_color = "pos" if c_pct >= 0 else "neg"
        c_arrow = "\u25b2" if c_pct >= 0 else "\u25bc"
        c_sign  = "+" if c_pct >= 0 else ""
        err_note= f' <span style="color:var(--red);font-size:10px;">data error</span>' if r["error"] else ""
        desc    = mc_descriptions.get(tk, mc_fallback.get(tk, ""))
        slug    = logo_slugs.get(tk, "")
        logo_html = f'<img src="https://s3-symbol-logo.tradingview.com/{slug}.svg" class="tkr-logo" alt="{tk} logo" onerror="this.style.display=\'none\'">' if slug else ""
        megacap_html += (
            f'<div class="co-row" data-ticker="{tk}">'
            f'<div class="tkr-wrap">{logo_html}<span class="tkr">{tk}</span></div>'
            f'<div class="co-body">'
            f'<div class="co-desc"><strong>{v["name"]}</strong>{err_note} {desc}</div>'
            f'<div class="co-stats">'
            f'<span class="co-stat"><span class="co-stat-lbl">Close</span> <span class="co-stat-val">${r["end_price"]:,.2f}</span></span>'
            f'<span class="co-stat"><span class="co-stat-lbl">$ Chg</span> <span class="co-stat-val {c_color}">{c_sign}${abs(c_abs):,.2f}</span></span>'
            f'<span class="co-stat"><span class="co-stat-lbl">5D High</span> <span class="co-stat-val">${r["week_high"]:,.2f}</span></span>'
            f'<span class="co-stat"><span class="co-stat-lbl">5D Low</span> <span class="co-stat-val">${r["week_low"]:,.2f}</span></span>'
            f'</div>'
            f'</div>'
            f'<span class="co-mv {c_color}">{c_arrow} {c_sign}{c_pct}%</span>'
            f'</div>'
        )

    # Claude: section 08 lookahead
    print("Generating Section 08 via Claude...")
    lookahead_context = {
        "sp_pct": sp_pct, "nd_pct": nd["pct_change"],
        "vix_close": vix_close, "tnx_close": tnx["end_price"], "tnx_pct": tnx_pct,
        "dxy_close": dxy["end_price"], "dxy_pct": dxy["pct_change"],
        "top_sectors": ", ".join(s[0] for s in top_sectors[:2]),
        "bottom_sectors": ", ".join(s[0] for s in bottom_sectors[:2]),
        "btc_pct": btc["pct_change"], "oil_pct": oil["pct_change"], "gold_pct": gold["pct_change"],
        "week_end_date": week_end_date,
    }
    lookahead = generate_lookahead_claude(lookahead_context) if ai_enabled else build_lookahead_fallback(lookahead_context)
    lookahead = sanitize_text_map(lookahead)

    # Claude: global market status
    print("Generating global market context via Claude...")
    global_prompt = (
        "You are writing one-sentence status descriptions for a weekly global equity market summary. "
        "Each sentence must be specific to the index named and its actual performance — do not be generic. "
        "Do NOT start with the index name. Start with the insight or dynamic directly. "
        "Respond ONLY with JSON with keys nikkei, stoxx, ftse, hsi. No markdown.\n"
        f"Nikkei 225 (Japan): {'+' if n225['pct_change'] >= 0 else ''}{n225['pct_change']}% WTD, close {n225['end_price']:,.2f}\n"
        f"Euro Stoxx 50 (EU): {'+' if stoxx['pct_change'] >= 0 else ''}{stoxx['pct_change']}% WTD, close {stoxx['end_price']:,.2f}\n"
        f"FTSE 100 (UK): {'+' if ftse['pct_change'] >= 0 else ''}{ftse['pct_change']}% WTD, close {ftse['end_price']:,.2f}\n"
        f"Hang Seng (HK): {'+' if hsi['pct_change'] >= 0 else ''}{hsi['pct_change']}% WTD, close {hsi['end_price']:,.2f}\n"
        f"S&P 500 context: {'+' if sp_pct >= 0 else ''}{sp_pct}% WTD, VIX {vix_close:.2f}, 10-yr yield {tnx['end_price']:.2f}%"
    )
    global_fallback = {
        "nikkei": "Japanese equities tracked broader global momentum flows this week.",
        "stoxx":  "European blue-chip stocks digested the latest economic policy signaling.",
        "ftse":   "UK large-caps reflected commodity sensitivity and sterling moves against the dollar.",
        "hsi":    "Hong Kong shares traded on China policy cues and tech sector sentiment.",
    }
    global_status = claude_json(global_prompt, required_keys={"nikkei","stoxx","ftse","hsi"}, max_tokens=300, fallback=global_fallback) if ai_enabled else global_fallback
    global_status = sanitize_text_map(global_status)

    # Claude: crypto descriptions
    print("Generating crypto descriptions via Claude...")
    crypto_prompt = (
        "You are writing one-sentence analytical notes for a weekly cryptocurrency market summary. "
        "Each sentence must be specific to the asset and its actual performance this week — no generic phrasing. "
        "Do NOT start the sentence with the asset name. Start with the action, dynamic, or insight directly. "
        "Respond ONLY with JSON with keys btc, eth, sol, xrp. No markdown.\n"
        f"Bitcoin (BTC): {'+' if btc['pct_change'] >= 0 else ''}{btc['pct_change']}% WTD, close ${btc['end_price']:,.0f}, 5D high ${btc['week_high']:,.0f}, 5D low ${btc['week_low']:,.0f}\n"
        f"Ethereum (ETH): {'+' if eth['pct_change'] >= 0 else ''}{eth['pct_change']}% WTD, close ${eth['end_price']:,.0f}, 5D high ${eth['week_high']:,.0f}, 5D low ${eth['week_low']:,.0f}\n"
        f"Solana (SOL): {'+' if sol['pct_change'] >= 0 else ''}{sol['pct_change']}% WTD, close ${sol['end_price']:.2f}\n"
        f"XRP: {'+' if xrp['pct_change'] >= 0 else ''}{xrp['pct_change']}% WTD, close ${xrp['end_price']:.4f}\n"
        f"Equity context: S&P 500 {'+' if sp_pct >= 0 else ''}{sp_pct}% WTD, VIX {vix_close:.2f}"
    )
    crypto_fallback = {
        "btc": f"Closed at ${btc['end_price']:,.0f} with a 5-day range of ${btc['week_low']:,.0f}–${btc['week_high']:,.0f}, tracking broad risk sentiment.",
        "eth": f"Settled at ${eth['end_price']:,.0f}, with relative performance to BTC reflecting shifts in layer-1 narrative flow.",
        "sol": f"Finished at ${sol['end_price']:.2f}, moving in line with broader high-beta crypto exposure.",
        "xrp": f"Printed at ${xrp['end_price']:.4f}, with regulatory and payments-sector headlines driving the tape.",
    }
    crypto_descriptions = claude_json(crypto_prompt, required_keys={"btc","eth","sol","xrp"}, max_tokens=400, fallback=crypto_fallback) if ai_enabled else crypto_fallback
    crypto_descriptions = sanitize_text_map(crypto_descriptions)

    # TradingView crypto logos (with fallback hiding on error)
    # Pattern: s3-symbol-logo.tradingview.com/crypto/XTVC{SYMBOL}.svg
    def crypto_card(name, symbol, tv_symbol, price_str, data, desc):
        c_pct   = data["pct_change"]
        c_color = "pos" if c_pct >= 0 else "neg"
        c_arrow = "\u25b2" if c_pct >= 0 else "\u25bc"
        c_sign  = "+" if c_pct >= 0 else ""
        logo    = f'https://s3-symbol-logo.tradingview.com/crypto/XTVC{tv_symbol}.svg'
        return (
            f'<div class="cc">'
            f'<div class="cc-head">'
            f'<img src="{logo}" class="cc-logo" alt="{symbol} logo" onerror="this.style.display=\'none\'">'
            f'<div class="cc-name">{name} ({symbol})</div>'
            f'</div>'
            f'<div class="cc-price">{price_str}</div>'
            f'<div class="cc-chg {c_color}">{c_arrow} {c_sign}{c_pct}% WTD</div>'
            f'<div class="cc-range"><span class="cc-range-lbl">5D Range</span> '
            f'<span class="cc-range-val">${data["week_low"]:,.2f} – ${data["week_high"]:,.2f}</span></div>'
            f'<div class="cc-desc">{desc}</div>'
            f'</div>'
        )

    crypto_html = (
        crypto_card("Bitcoin", "BTC", "BTC", f"${btc['end_price']:,.0f}", btc, crypto_descriptions["btc"])
      + crypto_card("Ethereum", "ETH", "ETH", f"${eth['end_price']:,.0f}", eth, crypto_descriptions["eth"])
      + crypto_card("Solana", "SOL", "SOL", f"${sol['end_price']:.2f}", sol, crypto_descriptions["sol"])
      + crypto_card("XRP", "XRP", "XRP", f"${xrp['end_price']:.4f}", xrp, crypto_descriptions["xrp"])
    )

    # Claude: investor takeaway
    print("Generating investor takeaway via Claude...")
    direction = "higher" if sp_pct >= 0 else "lower"
    vix_note  = "elevated hedging activity" if vix_close >= 20 else "subdued volatility"
    takeaway_prompt = (
        "You are a senior equity strategist writing the Investor Takeaway for a weekly market summary. "
        "Write exactly 3 sentences — sharp, analytical, institutional in tone. No bullet points. No headers. "
        "Synthesize what happened, why it happened, and what it implies for positioning next week. "
        "Do not be generic. Reference specific numbers, sector leadership/laggards, volatility, and rates where relevant.\n"
        f"S&P 500: {sp['end_price']:,.2f} ({'+' if sp_pct >= 0 else ''}{sp_pct}% WTD)\n"
        f"Nasdaq: {nd['end_price']:,.2f} ({'+' if nd['pct_change'] >= 0 else ''}{nd['pct_change']}% WTD)\n"
        f"DJIA: {dj['end_price']:,.2f} ({'+' if dj['pct_change'] >= 0 else ''}{dj['pct_change']}% WTD)\n"
        f"VIX: {vix_close:.2f} ({'+' if vix['pct_change'] >= 0 else ''}{vix['pct_change']}% WTD)\n"
        f"10-Yr Yield: {tnx['end_price']:.2f}% ({'+' if tnx_pct >= 0 else ''}{tnx_pct}% WTD)\n"
        f"DXY: {dxy['end_price']:.2f} ({'+' if dxy['pct_change'] >= 0 else ''}{dxy['pct_change']}% WTD)\n"
        f"Gold: {gold['end_price']:,.2f} ({'+' if gold['pct_change'] >= 0 else ''}{gold['pct_change']}% WTD)\n"
        f"Crude Oil: {oil['end_price']:,.2f} ({'+' if oil['pct_change'] >= 0 else ''}{oil['pct_change']}% WTD)\n"
        f"Bitcoin: {btc['end_price']:,.0f} ({'+' if btc['pct_change'] >= 0 else ''}{btc['pct_change']}% WTD)\n"
        f"Top sectors: {', '.join(f'{s[0]} {chr(43) if s[1] >= 0 else str(s[1])}%' for s in top_sectors)}\n"
        f"Bottom sectors: {', '.join(f'{s[0]} {chr(43) if s[1] >= 0 else str(s[1])}%' for s in bottom_sectors)}\n"
        f"Nikkei 225: {'+' if n225['pct_change'] >= 0 else ''}{n225['pct_change']}% WTD\n"
        f"Euro Stoxx 50: {'+' if stoxx['pct_change'] >= 0 else ''}{stoxx['pct_change']}% WTD"
    )
    takeaway_fallback = (
        f"U.S. equities closed the week {direction}, with the S&amp;P 500 finishing at {sp['end_price']:,.2f} "
        f"and the VIX at {vix_close:.2f}, signaling {vix_note}. "
        f"Leadership remained selective: {top_sectors[0][0]} led the tape while {bottom_sectors[0][0]} lagged, "
        f"keeping the market dependent on growth and AI-linked momentum rather than broad participation. "
        f"For next week, the key test is whether rates at {tnx['end_price']:.2f}% and the dollar at {dxy['end_price']:.2f} "
        f"stay contained enough for risk appetite to broaden beyond the current winners."
    )
    takeaway_text = claude(takeaway_prompt, max_tokens=400, fallback=takeaway_fallback) if ai_enabled else takeaway_fallback
    takeaway_text = render_html_text(takeaway_text)

    # Build ticker bar
    t_items = (
        get_t_item("S&P 500",      f"{sp['end_price']:,.2f}",   sp_pct)
      + get_t_item("Nasdaq",       f"{nd['end_price']:,.2f}",   nd["pct_change"])
      + get_t_item("DJIA",         f"{dj['end_price']:,.2f}",   dj["pct_change"], abs_val=dj["abs_change"], is_points=True)
      + get_t_item("Russell 2000", f"{rut['end_price']:,.2f}",  rut["pct_change"])
      + get_t_item("Crude Oil",    f"${oil['end_price']:,.2f}", oil["pct_change"])
      + get_t_item("Gold",         f"${gold['end_price']:,.2f}",gold["pct_change"])
      + get_t_item("VIX",          f"{vix_close:.2f}",          vix["pct_change"])
      + get_t_item("Bitcoin",      f"${btc['end_price']:,.0f}", btc["pct_change"])
      + get_t_item("Ethereum",     f"${eth['end_price']:,.0f}", eth["pct_change"])
      + get_t_item("10-Yr Yield",  f"{tnx['end_price']:.2f}%",  tnx_pct, abs_val=tnx["abs_change"], is_yield=True)
    )
    ticker_html = f'<div class="ticker-wrapper"><div class="ticker-track">{t_items}{t_items}</div></div>'

    market_tone  = "\u25b2 RISK-ON RALLY"   if sp_pct >= 0 else "\u25bc RISK-OFF PULLBACK"
    badge_color  = "badge-green"             if sp_pct >= 0 else "badge-red"
    sp_card_class= "up"                      if sp_pct >= 0 else ""
    nd_card_class= "up"                      if nd["pct_change"] >= 0 else ""
    dj_card_class= "up"                      if dj["pct_change"] >= 0 else ""

    top_tags = "".join(f'<span class="tag g">{s[0]} ({chr(43) if s[1] >= 0 else ""}{s[1]}%)</span>' for s in top_sectors)
    bot_tags = "".join(f'<span class="tag r">{s[0]} ({chr(43) if s[1] >= 0 else ""}{s[1]}%)</span>' for s in bottom_sectors)

    sp_chart = fetch_weekly_chart_data("^GSPC", start_date=report_start, end_date=week_end)
    sp_dates = sp_chart["dates"]
    sp_data  = sp_chart["closes"]

    spy = fetch_weekly_data("SPY", start_date=previous_week_end, end_date=week_end)
    rspy = fetch_weekly_data("RSP", start_date=previous_week_end, end_date=week_end)
    advances = sum(1 for value in sector_perf.values() if value > 0)
    declines = sum(1 for value in sector_perf.values() if value < 0)
    breadth_share = round((advances / len(sector_perf)) * 100, 1) if sector_perf else 0.0
    breadth_summary = (
        f"{advances} of {len(sector_perf)} sectors finished positive, while {declines} declined."
        if sector_perf else "Sector breadth data was unavailable."
    )
    breadth_cards = {
        "Cap-Weighted S&P 500": f"{sp_pct:+.2f}%",
        "Equal-Weight S&P 500": f"{rspy['pct_change']:+.2f}%" if not rspy.get("error") else "N/A",
        "SPY ETF Check": f"{spy['pct_change']:+.2f}%" if not spy.get("error") else "N/A",
        "Positive Sector Share": f"{breadth_share:.1f}%"
    }
    breadth_html = "".join(
        f'<div class="dcell"><div class="dc-lbl">{render_html_text(label)}</div><div class="dc-val">{render_html_text(value)}</div></div>'
        for label, value in breadth_cards.items()
    )

    # Global market table rows (Section 06)
    def global_row(name, data, status_text):
        color = "pos" if data["pct_change"] >= 0 else "neg"
        sign  = "+" if data["pct_change"] >= 0 else ""
        return (
            f'<tr>'
            f'<td>{name}</td>'
            f'<td>{data["end_price"]:,.2f}</td>'
            f'<td class="{color}">{sign}{data["pct_change"]}%</td>'
            f'<td>{status_text}</td>'
            f'</tr>'
        )

    global_rows_html = (
        global_row("Nikkei 225 (Japan)", n225, global_status["nikkei"])
      + global_row("Euro Stoxx 50 (EU)", stoxx, global_status["stoxx"])
      + global_row("FTSE 100 (UK)", ftse, global_status["ftse"])
      + global_row("Hang Seng (HK)", hsi, global_status["hsi"])
    )


    tradingview_widget_html = """  <div class="section tradingview-section">
    <div class="tradingview-card">
      <!-- TradingView Widget BEGIN -->
      <div class="tradingview-widget-container">
        <div class="tradingview-widget-container__widget"></div>
        <div class="tradingview-widget-copyright"><a href="https://www.tradingview.com/markets/" rel="noopener nofollow" target="_blank"><span class="blue-text">World markets</span></a> by TradingView</div>
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>
        {
        "lineWidth": 2,
        "lineType": 0,
        "chartType": "area",
        "fontColor": "rgb(106, 109, 120)",
        "gridLineColor": "rgba(242, 242, 242, 0.06)",
        "volumeUpColor": "rgba(34, 171, 148, 0.5)",
        "volumeDownColor": "rgba(247, 82, 95, 0.5)",
        "backgroundColor": "#0F0F0F",
        "widgetFontColor": "#DBDBDB",
        "upColor": "#22ab94",
        "downColor": "#f7525f",
        "borderUpColor": "#22ab94",
        "borderDownColor": "#f7525f",
        "wickUpColor": "#22ab94",
        "wickDownColor": "#f7525f",
        "colorTheme": "dark",
        "isTransparent": false,
        "locale": "en",
        "chartOnly": false,
        "scalePosition": "right",
        "scaleMode": "Normal",
        "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
        "valuesTracking": "1",
        "changeMode": "price-and-percent",
        "symbols": [
          [
            "NASDAQ:AAPL|1D"
          ],
          [
            "NASDAQ:MSFT|1D"
          ],
          [
            "NASDAQ:NVDA|1D"
          ],
          [
            "NASDAQ:AMZN|1D"
          ],
          [
            "NASDAQ:META|1D"
          ],
          [
            "NASDAQ:SNDK|1D"
          ],
          [
            "amd|1D"
          ],
          [
            "NASDAQ:INTC|1D"
          ],
          [
            "NASDAQ:MU|1D"
          ]
        ],
        "dateRanges": [
          "1d|1",
          "1m|30",
          "3m|60",
          "12m|1D",
          "60m|1W",
          "all|1M"
        ],
        "fontSize": "10",
        "headerFontSize": "medium",
        "autosize": false,
        "width": "100%",
        "height": "520",
        "noTimeScale": false,
        "hideDateRanges": false,
        "hideMarketStatus": false,
        "hideSymbolLogo": false
      }
        </script>
      </div>
      <!-- TradingView Widget END -->
    </div>
  </div>
"""

    def dedupe_tradingview_widget_sections(html):
        """Keep a single TradingView widget block if a merge/regeneration duplicates it."""
        first_idx = html.find(tradingview_widget_html)
        if first_idx == -1:
            return html
        search_from = first_idx + len(tradingview_widget_html)
        next_idx = html.find(tradingview_widget_html, search_from)
        while next_idx != -1:
            html = html[:next_idx] + html[next_idx + len(tradingview_widget_html):]
            next_idx = html.find(tradingview_widget_html, search_from)
        return html

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Market Summary &ndash; {week_start_str}&ndash;{today_str}, {year_str}</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #05050d;
    --surface: rgba(255,255,255,0.07);
    --surface2: rgba(255,255,255,0.04);
    --surface3: rgba(255,255,255,0.02);
    --border: rgba(255,255,255,0.08);
    --accent: #0a84ff;
    --accent2: #bf5af2;
    --green: #30d158;
    --red: #ff453a;
    --text: rgba(255,255,255,0.92);
    --muted: rgba(255,255,255,0.4);
    --label: rgba(255,255,255,0.6);
    --nav-bg: rgba(5,5,13,0.55);
    --title-color: rgba(255,255,255,0.95);
    --glass-sheen: rgba(255,255,255,0.06);
    --glass-border: rgba(255,255,255,0.12);
    --blob1: rgba(108,92,231,0.18);
    --blob2: rgba(0,206,201,0.15);
    --blob3: rgba(253,121,168,0.14);
    --badge-green-bg: rgba(48,209,88,0.15);
    --badge-green-border: rgba(48,209,88,0.25);
    --badge-red-bg: rgba(255,69,58,0.15);
    --badge-red-border: rgba(255,69,58,0.25);
    --scrollbar-thumb: rgba(255,255,255,0.12);
    --scrollbar-hover: rgba(255,255,255,0.22);
    --shadow-dark: 0 8px 32px rgba(0,0,0,0.28);
    --shadow-glow: 0 24px 48px rgba(0,0,0,0.4);
    --shadow-glass: 0 8px 32px rgba(0,0,0,0.18);
    --shadow-glass-hover: 0 24px 48px rgba(0,0,0,0.32);
    --theme-hover-bg: rgba(10,132,255,0.20);
    --accent-border: rgba(10,132,255,0.60);
    --chart-fill-top: rgba(10,132,255,0.25);
    --chart-fill-bottom: rgba(10,132,255,0.02);
    --chart-grid: rgba(255,255,255,0.08);
    --chart-point-bg: rgba(255,255,255,1);
    --transparent: transparent;
  }}

  :root.light {{
    --bg: #f2f2f7;
    --surface: rgba(255,255,255,0.62);
    --surface2: rgba(255,255,255,0.42);
    --surface3: rgba(255,255,255,0.28);
    --border: rgba(0,0,0,0.06);
    --accent: #007aff;
    --accent2: #af52de;
    --green: #34c759;
    --red: #ff3b30;
    --text: #1c1c1e;
    --muted: #6e6e73;
    --label: #3a3a3c;
    --nav-bg: rgba(242,242,247,0.72);
    --title-color: #1c1c1e;
    --glass-sheen: rgba(255,255,255,0.55);
    --glass-border: rgba(255,255,255,0.75);
    --blob1: rgba(175,160,255,0.12);
    --blob2: rgba(100,210,255,0.10);
    --blob3: rgba(255,180,210,0.10);
    --badge-green-bg: rgba(52,199,89,0.12);
    --badge-green-border: rgba(52,199,89,0.20);
    --badge-red-bg: rgba(255,59,48,0.12);
    --badge-red-border: rgba(255,59,48,0.20);
    --scrollbar-thumb: rgba(0,0,0,0.12);
    --scrollbar-hover: rgba(0,0,0,0.20);
    --shadow-dark: 0 8px 32px rgba(0,0,0,0.08);
    --shadow-glow: 0 24px 48px rgba(0,0,0,0.14);
    --shadow-glass: 0 8px 32px rgba(0,0,0,0.08);
    --shadow-glass-hover: 0 24px 48px rgba(0,0,0,0.14);
    --theme-hover-bg: rgba(0,122,255,0.20);
    --accent-border: rgba(0,122,255,0.60);
    --chart-fill-top: rgba(0,122,255,0.22);
    --chart-fill-bottom: rgba(0,122,255,0.03);
    --chart-grid: rgba(0,0,0,0.08);
    --chart-point-bg: rgba(255,255,255,1);
    --transparent: transparent;
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease, box-shadow 0.3s ease;
  }}

  *::before,
  *::after {{
    box-sizing: border-box;
    transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease, box-shadow 0.3s ease;
  }}

  html {{
    background: var(--bg);
    scroll-behavior: smooth;
  }}

  body {{
    min-height: 100vh;
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', system-ui, sans-serif;
    font-weight: 400;
    line-height: 1.6;
    overflow-x: hidden;
  }}

  a {{
    color: var(--text);
    text-decoration: none;
  }}

  .header-font {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    letter-spacing: -0.02em;
  }}

  ::-webkit-scrollbar {{ width: 9px; }}
  ::-webkit-scrollbar-track {{ background: var(--transparent); }}
  ::-webkit-scrollbar-thumb {{
    background: var(--scrollbar-thumb);
    border-radius: 999px;
  }}
  ::-webkit-scrollbar-thumb:hover {{ background: var(--scrollbar-hover); }}

  .aurora-bg,
  .blob,
  canvas,
  .ticker-track {{
    transition: none !important;
  }}

  .aurora-bg {{
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    overflow: hidden;
  }}

  .blob {{
    position: fixed;
    z-index: 0;
    border-radius: 50%;
    filter: blur(120px);
    pointer-events: none;
    animation: float 28s ease-in-out infinite;
  }}

  .b1 {{
    width: 600px;
    height: 600px;
    top: -180px;
    right: -160px;
    background: var(--blob1);
    animation-delay: 0s;
  }}

  .b2 {{
    width: 500px;
    height: 500px;
    bottom: -180px;
    left: -160px;
    background: var(--blob2);
    animation-delay: -10s;
  }}

  .b3 {{
    width: 400px;
    height: 400px;
    top: 36%;
    right: 8%;
    background: var(--blob3);
    animation-delay: -18s;
  }}

  @keyframes float {{
    0%, 100% {{ transform: translate(0, 0) scale(1); }}
    33% {{ transform: translate(40px, -30px) scale(1.05); }}
    66% {{ transform: translate(-20px, 20px) scale(0.97); }}
  }}

  .top-nav-wrapper,
  .container,
  .footer {{
    position: relative;
    z-index: 1;
  }}

  .top-nav-wrapper {{
    position: sticky;
    top: 0;
    z-index: 1000;
    background: var(--nav-bg);
    backdrop-filter: blur(48px) saturate(200%);
    -webkit-backdrop-filter: blur(48px) saturate(200%);
    border-bottom: 1px solid var(--border);
  }}

  .masthead {{
    padding: 28px 60px 20px;
    position: relative;
    overflow: hidden;
  }}

  .masthead::before {{
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, var(--glass-sheen) 0%, var(--transparent) 50%);
    pointer-events: none;
  }}

  .masthead-row {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 20px;
    position: relative;
    z-index: 1;
  }}

  .kicker {{
    font-size: 10px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 600;
    margin-bottom: 8px;
  }}

  .week-title {{
    font-size: clamp(28px, 4vw, 48px);
    line-height: 1.05;
    color: var(--title-color);
  }}

  .week-title span {{ color: var(--accent); }}

  .masthead-meta {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }}

  .badge {{
    font-size: 10px;
    letter-spacing: 0.08em;
    padding: 6px 14px;
    border-radius: 9999px;
    font-weight: 700;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
  }}

  .badge-green {{
    background: var(--badge-green-bg);
    color: var(--green);
    border: 1px solid var(--badge-green-border);
  }}

  .badge-red {{
    background: var(--badge-red-bg);
    color: var(--red);
    border: 1px solid var(--badge-red-border);
  }}

  .pub-date {{
    font-size: 10.5px;
    color: var(--muted);
    font-weight: 500;
  }}

  .theme-btn {{
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--glass-border);
    border-radius: 50%;
    width: 38px;
    height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    cursor: pointer;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    transition: all 0.25s ease;
    box-shadow: var(--shadow-dark);
  }}

  .theme-btn:hover {{
    transform: scale(1.08);
    background: var(--theme-hover-bg);
    border-color: var(--accent);
  }}

  .ticker-wrapper {{
    border-top: 1px solid var(--border);
    overflow: hidden;
    background: var(--transparent);
  }}

  .ticker-track {{
    display: flex;
    width: max-content;
    animation: scrollTicker 60s linear infinite;
    will-change: transform;
  }}

  .ticker-track:hover {{ animation-play-state: paused; }}

  @keyframes scrollTicker {{
    from {{ transform: translateX(0); }}
    to {{ transform: translateX(-50%); }}
  }}

  .t-item {{
    display: inline-flex;
    flex-direction: column;
    gap: 3px;
    padding: 14px 32px;
    flex-shrink: 0;
    border-right: 1px solid var(--border);
  }}

  .t-name {{
    font-size: 9px;
    letter-spacing: 0.1em;
    color: var(--muted);
    text-transform: uppercase;
    font-weight: 600;
  }}

  .t-val,
  .idx-close,
  .dc-val,
  .co-stat-val,
  .cc-price,
  .cc-range-val,
  .gtable td:nth-child(2) {{
    font-variant-numeric: tabular-nums;
  }}

  .t-val {{
    font-size: 15px;
    font-weight: 700;
  }}

  .t-chg {{
    font-size: 10.5px;
    font-weight: 700;
  }}

  .neg {{ color: var(--red); }}
  .pos {{ color: var(--green); }}

  .container {{
    max-width: 1180px;
    margin: 0 auto;
    padding: 0 60px 80px;
  }}

  .section {{
    margin-top: 68px;
    padding-top: 52px;
    border-top: 1px solid var(--border);
  }}

  .section:first-child {{
    margin-top: 12px;
    padding-top: 32px;
    border-top: none;
  }}

  .sec-label {{
    font-size: 10px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 700;
    margin-bottom: 8px;
  }}

  .sec-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 26px;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin-bottom: 24px;
    color: var(--text);
  }}

  .sec-intro {{
    font-size: 14px;
    color: var(--label);
    line-height: 1.65;
    margin-bottom: 24px;
    max-width: 820px;
  }}

  .idx-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 12px;
    margin-bottom: 28px;
  }}

  .idx-card,
  .dcell,
  .cc,
  .ahead-cell,
  .co-list,
  .takeaway,
  .chart-wrap,
  .tradingview-card,
  .table-wrap {{
    position: relative;
    background: var(--surface);
    border: 1px solid var(--glass-border);
    backdrop-filter: blur(40px) saturate(180%);
    -webkit-backdrop-filter: blur(40px) saturate(180%);
    box-shadow: var(--shadow-glass), inset 0 1px 0 var(--glass-sheen);
    overflow: hidden;
  }}

  .idx-card::before,
  .dcell::before,
  .cc::before,
  .ahead-cell::before,
  .co-list::before,
  .takeaway::before,
  .chart-wrap::before,
  .tradingview-card::before,
  .table-wrap::before {{
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(135deg, var(--glass-sheen) 0%, var(--transparent) 50%);
    pointer-events: none;
  }}

  .idx-card:hover,
  .dcell:hover,
  .cc:hover,
  .ahead-cell:hover,
  .co-list:hover,
  .takeaway:hover,
  .chart-wrap:hover,
  .tradingview-card:hover,
  .table-wrap:hover {{
    transform: translateY(-6px);
    box-shadow: var(--shadow-glass-hover), inset 0 1px 0 var(--glass-sheen);
  }}

  .idx-card,
  .dcell,
  .cc,
  .ahead-cell,
  .takeaway {{
    border-radius: 20px;
  }}

  .co-list,
  .chart-wrap,
  .tradingview-card,
  .table-wrap {{
    border-radius: 24px;
  }}

  .idx-card {{
    cursor: pointer;
    padding: 28px;
  }}

  .idx-card.up::after {{
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: var(--green);
    border-radius: 0 0 20px 20px;
  }}

  .idx-name {{
    font-size: 10.5px;
    letter-spacing: 0.12em;
    color: var(--muted);
    font-weight: 600;
    margin-bottom: 8px;
    text-transform: uppercase;
  }}

  .idx-close {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 32px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 8px;
    color: var(--text);
  }}

  .idx-wtd {{
    font-size: 13px;
    margin-bottom: 12px;
    font-weight: 600;
  }}

  .idx-note {{
    font-size: 13px;
    color: var(--label);
    line-height: 1.55;
  }}

  .blist {{
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }}

  .blist li {{
    padding-left: 24px;
    position: relative;
    font-size: 14.5px;
    line-height: 1.65;
    color: var(--text);
  }}

  .blist li::before {{
    content: '→';
    position: absolute;
    left: 0;
    top: 0;
    color: var(--accent);
    font-size: 18px;
    line-height: 1.2;
  }}

  .blist li strong {{ font-weight: 700; }}

  .two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 48px;
  }}

  .col-lbl {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    margin-bottom: 12px;
  }}

  .col-lbl.lead {{ color: var(--green); }}
  .col-lbl.lag {{ color: var(--red); }}

  .tag-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 20px;
  }}

  .tag {{
    font-size: 11px;
    padding: 5px 14px;
    border-radius: 9999px;
    font-weight: 600;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
  }}

  .tag.g {{
    background: var(--badge-green-bg);
    color: var(--green);
    border: 1px solid var(--badge-green-border);
  }}

  .tag.r {{
    background: var(--badge-red-bg);
    color: var(--red);
    border: 1px solid var(--badge-red-border);
  }}

  .data-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 12px;
    margin-bottom: 32px;
  }}

  .dcell,
  .ahead-cell,
  .cc {{
    padding: 24px;
  }}

  .dc-lbl,
  .co-stat-lbl,
  .cc-range-lbl {{
    font-size: 10px;
    letter-spacing: 0.12em;
    color: var(--muted);
    text-transform: uppercase;
    font-weight: 700;
  }}

  .dc-lbl {{ margin-bottom: 6px; }}

  .dc-val {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 6px;
    line-height: 1.1;
    color: var(--text);
  }}

  .dc-val.hot {{ color: var(--red); }}
  .dc-val.warm {{ color: var(--accent2); }}
  .dc-val.cool {{ color: var(--green); }}

  .dc-note {{
    font-size: 13px;
    color: var(--label);
    line-height: 1.55;
  }}

  .co-list {{
    padding: 6px 24px;
  }}

  .co-row {{
    display: flex;
    align-items: flex-start;
    gap: 18px;
    padding: 22px 0;
    border-bottom: 1px solid var(--border);
    position: relative;
    z-index: 1;
  }}

  .co-row:last-child {{ border-bottom: none; }}

  .tkr-wrap {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }}

  .tkr-logo,
  .cc-logo {{
    border-radius: 50%;
    object-fit: contain;
    background: var(--surface2);
    border: 1px solid var(--glass-border);
    box-shadow: var(--shadow-dark);
  }}

  .tkr-logo {{
    width: 40px;
    height: 40px;
    padding: 5px;
  }}

  .tkr {{
    font-size: 11px;
    font-weight: 700;
    background: var(--surface2);
    border: 1px solid var(--border);
    padding: 4px 12px;
    border-radius: 8px;
    color: var(--text);
    min-width: 70px;
    text-align: center;
  }}

  .co-body {{
    flex: 1;
    min-width: 0;
  }}

  .co-desc {{
    font-size: 14.5px;
    line-height: 1.65;
    color: var(--text);
    margin-bottom: 10px;
  }}

  .co-desc strong {{ font-weight: 700; }}

  .co-stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    font-size: 12px;
    padding-top: 8px;
    border-top: 1px dashed var(--border);
  }}

  .co-stat {{
    display: inline-flex;
    gap: 6px;
    align-items: baseline;
  }}

  .co-stat-lbl {{ font-size: 9.5px; }}

  .co-stat-val {{
    font-weight: 700;
    color: var(--text);
    font-family: 'Space Grotesk', sans-serif;
  }}

  .co-mv {{
    font-size: 14px;
    font-weight: 700;
    margin-top: 4px;
    white-space: nowrap;
  }}

  .crypto-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin-bottom: 32px;
  }}

  .cc {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}

  .cc-head {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}

  .cc-logo {{
    width: 32px;
    height: 32px;
    padding: 3px;
    flex-shrink: 0;
  }}

  .cc-name {{
    font-size: 11px;
    letter-spacing: 0.12em;
    color: var(--muted);
    text-transform: uppercase;
    font-weight: 700;
  }}

  .cc-price {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 28px;
    font-weight: 700;
    line-height: 1;
    color: var(--text);
  }}

  .cc-chg {{
    font-size: 13px;
    font-weight: 700;
  }}

  .cc-range {{
    font-size: 11.5px;
    color: var(--label);
    display: flex;
    gap: 8px;
    align-items: baseline;
    padding-top: 4px;
    border-top: 1px dashed var(--border);
  }}

  .cc-range-val {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    color: var(--text);
  }}

  .cc-desc {{
    font-size: 13px;
    line-height: 1.6;
    color: var(--label);
  }}

  .table-wrap {{ overflow: hidden; }}

  .gtable {{
    width: 100%;
    border-collapse: collapse;
    position: relative;
    z-index: 1;
  }}

  .gtable th {{
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    padding: 14px 18px;
    text-align: left;
    border-bottom: 1px solid var(--border);
    font-weight: 700;
    background: var(--surface3);
  }}

  .gtable td {{
    padding: 16px 18px;
    font-size: 14px;
    color: var(--text);
    border-bottom: 1px solid var(--border);
    vertical-align: top;
    line-height: 1.6;
  }}

  .gtable tr:last-child td {{ border-bottom: none; }}
  .gtable td:first-child {{ font-weight: 700; white-space: nowrap; }}
  .gtable td:nth-child(2) {{ font-weight: 700; width: 120px; font-family: 'Space Grotesk', sans-serif; }}
  .gtable td:nth-child(3) {{ font-weight: 700; width: 100px; }}

  .takeaway {{
    border-left: 2px solid var(--accent-border);
    padding: 32px 36px;
    font-size: 15px;
    line-height: 1.75;
    color: var(--text);
    backdrop-filter: blur(32px) saturate(180%);
    -webkit-backdrop-filter: blur(32px) saturate(180%);
    box-shadow: inset 0 0 0 1px var(--glass-border);
  }}

  .ahead-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }}

  .ahead-day {{
    font-size: 10px;
    letter-spacing: 0.12em;
    color: var(--accent);
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 10px;
  }}

  .ahead-ev {{
    font-size: 14px;
    line-height: 1.65;
    color: var(--text);
  }}

  .chart-wrap {{
    padding: 24px 28px;
  }}

  .chart-hdr {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    gap: 12px;
    flex-wrap: wrap;
    position: relative;
    z-index: 1;
  }}

  .chart-area {{
    position: relative;
    z-index: 1;
    height: 280px;
    max-height: 280px;
    overflow: hidden;
  }}

  .chart-canvas {{
    display: block;
    width: 100% !important;
    height: 280px !important;
    max-height: 280px !important;
  }}

  .chart-lbl {{
    font-size: 10px;
    letter-spacing: 0.12em;
    color: var(--muted);
    text-transform: uppercase;
    font-weight: 700;
  }}

  .tradingview-card {{
    height: 520px;
  }}

  .tradingview-card .tradingview-widget-container,
  .tradingview-card .tradingview-widget-container__widget,
  .tradingview-card iframe {{
    position: relative;
    z-index: 1;
    width: 100% !important;
    height: 100% !important;
  }}

  .tradingview-card .tradingview-widget-copyright {{
    position: absolute;
    left: 0;
    right: 0;
    bottom: 8px;
    z-index: 2;
    padding: 0 14px;
    font-size: 11px;
    color: var(--muted);
    text-align: center;
  }}

  .tradingview-card .tradingview-widget-copyright a {{
    color: var(--accent);
  }}

  .footer {{
    border-top: 1px solid var(--border);
    padding: 32px 60px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 10.5px;
    color: var(--muted);
  }}

  @media (max-width: 980px) {{
    .two-col,
    .ahead-grid {{ grid-template-columns: 1fr; }}
  }}

  @media (max-width: 820px) {{
    .masthead,
    .container,
    .footer {{
      padding-left: 24px;
      padding-right: 24px;
    }}

    .idx-grid,
    .crypto-grid,
    .data-row {{ grid-template-columns: 1fr; }}

    .masthead-row,
    .chart-hdr {{ align-items: flex-start; }}
    .masthead-meta {{ justify-content: flex-start; }}
  }}

  @media (prefers-reduced-motion: reduce) {{
    * {{
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }}
  }}
</style>
</head>
<body>
<div class="aurora-bg" aria-hidden="true">
  <div class="blob b1"></div>
  <div class="blob b2"></div>
  <div class="blob b3"></div>
</div>
<div class="top-nav-wrapper">
  <div class="masthead">
    <div class="masthead-row">
      <div>
        <div class="kicker">WEEKLY MARKET SUMMARY &bull; U.S. EQUITIES &amp; DIGITAL ASSETS</div>
        <div class="week-title header-font">{week_start_str} &ndash; <span>{today_str}</span>, {year_str}</div>
      </div>
      <div class="masthead-meta">
        <div class="badge {badge_color}">{market_tone}</div>
        <div class="pub-date">Published {full_date} &bull; Post-Market Close</div>
        <button onclick="toggleTheme()" class="theme-btn" title="Toggle light/dark mode" aria-label="Toggle theme">&#x1F317;</button>
      </div>
    </div>
  </div>
  {ticker_html}
</div>

<div class="container">
  <div class="section">
    <div class="sec-label">SECTION 01</div>
    <div class="sec-title">Major U.S. Indices</div>
    <div class="idx-grid">
      <a href="https://www.perplexity.ai/finance/%5ESPX" target="_blank" rel="noopener noreferrer">
        <div class="idx-card {sp_card_class}">
          <div class="idx-name">S&amp;P 500</div>
          <div class="idx-close">{sp['end_price']:,.2f}</div>
          <div class="idx-wtd {'pos' if sp_pct >= 0 else 'neg'}">{'&#9650;' if sp_pct >= 0 else '&#9660;'} {'+' if sp_pct >= 0 else ''}{sp_pct}% WTD</div>
          <div class="idx-note">Broad-market benchmark reflecting the 500 largest U.S. companies.</div>
        </div>
      </a>
      <a href="https://www.perplexity.ai/finance/%5EIXIC" target="_blank" rel="noopener noreferrer">
        <div class="idx-card {nd_card_class}">
          <div class="idx-name">Nasdaq Composite</div>
          <div class="idx-close">{nd['end_price']:,.2f}</div>
          <div class="idx-wtd {'pos' if nd['pct_change'] >= 0 else 'neg'}">{'&#9650;' if nd['pct_change'] >= 0 else '&#9660;'} {'+' if nd['pct_change'] >= 0 else ''}{nd['pct_change']}% WTD</div>
          <div class="idx-note">Tech-driven index led by growth and semiconductor leaders.</div>
        </div>
      </a>
      <a href="https://www.perplexity.ai/finance/%5EDJI" target="_blank" rel="noopener noreferrer">
        <div class="idx-card {dj_card_class}">
          <div class="idx-name">Dow Jones Industrial Average</div>
          <div class="idx-close">{dj['end_price']:,.2f}</div>
          <div class="idx-wtd {'pos' if dj['pct_change'] >= 0 else 'neg'}">{'&#9650;' if dj['pct_change'] >= 0 else '&#9660;'} {'+' if dj['abs_change'] >= 0 else ''}{int(abs(dj['abs_change'])):,} pts WTD</div>
          <div class="idx-note">Price-weighted gauge of 30 blue-chip U.S. corporations.</div>
        </div>
      </a>
    </div>
    <ul class="blist">
      <li><strong>Market Tone:</strong> U.S. equities finished the week {'higher' if sp_pct >= 0 else 'lower'}, with the S&amp;P 500 recording a {'+' if sp_pct >= 0 else ''}{sp_pct}% move.</li>
      <li><strong>Volatility Profile:</strong> The VIX closed the week at {vix_close:.2f}. Levels below 20 generally indicate a calmer equity environment, while prints above 20 signal elevated hedging activity.</li>
    </ul>
  </div>

  <div class="section">
    <div class="sec-label">SECTION 02</div>
    <div class="sec-title">Sector Performance</div>
    <div class="two-col" style="margin-bottom:26px;">
      <div>
        <div class="col-lbl lead">&#9650; TOP PERFORMING SECTORS</div>
        <div class="tag-row">{top_tags}</div>
        <ul class="blist">
          <li>{sector_bullets['top_bullet1']}</li>
          <li>{sector_bullets['top_bullet2']}</li>
        </ul>
      </div>
      <div>
        <div class="col-lbl lag">&#9660; LAGGING SECTORS</div>
        <div class="tag-row">{bot_tags}</div>
        <ul class="blist">
          <li>{sector_bullets['bot_bullet1']}</li>
          <li>{sector_bullets['bot_bullet2']}</li>
        </ul>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="sec-label">SECTION 03</div>
    <div class="sec-title">Key Macro &amp; Rates Data</div>
    <div class="data-row">
      <div class="dcell">
        <div class="dc-lbl">10-Yr Treasury Yield</div>
        <div class="dc-val {'hot' if tnx['pct_change'] >= 0 else 'cool'}">{tnx['end_price']:.2f}%</div>
        <div class="dc-note">Yield {'rose' if tnx['pct_change'] >= 0 else 'fell'} WTD, acting as a primary driver for broader equity valuations and sector rotation.</div>
      </div>
      <div class="dcell">
        <div class="dc-lbl">U.S. Dollar Index (DXY)</div>
        <div class="dc-val {'hot' if dxy['pct_change'] >= 0 else 'cool'}">{dxy['end_price']:.2f}</div>
        <div class="dc-note">The dollar {'strengthened' if dxy['pct_change'] >= 0 else 'weakened'} by {abs(dxy['pct_change']):.2f}% over the 5-day period, impacting multinational revenue expectations.</div>
      </div>
      <div class="dcell">
        <div class="dc-lbl">13-Week T-Bill Yield</div>
        <div class="dc-val">{irx['end_price']:.2f}%</div>
        <div class="dc-note">Tracks closely with the Federal Funds Rate. Yield moved by {abs(irx['pct_change']):.2f}% this week.</div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="sec-label">SECTION 04</div>
    <div class="sec-title">Mega-Cap Tech &amp; AI Semiconductor Movers</div>
    <div class="sec-intro">Mega-cap platform companies and AI-linked semiconductor names drive a disproportionate share of index-level moves. Each row below shows the weekly close, absolute dollar change, and the intraweek 5-day high/low range alongside the analyst note.</div>
    <div class="co-list">{megacap_html}</div>
  </div>

{tradingview_widget_html}
  <div class="section">
    <div class="sec-label">SECTION 05</div>
    <div class="sec-title">Cryptocurrency Market Recap</div>
    <div class="sec-intro">Weekly performance across the four most-tracked digital assets. Each tile shows the closing price, WTD change, the intraweek 5-day range, and an analyst note on what drove the move.</div>
    <div class="crypto-grid">{crypto_html}</div>
  </div>

  <div class="section">
    <div class="sec-label">SECTION 06</div>
    <div class="sec-title">Global Market Context</div>
    <div class="sec-intro">Non-U.S. developed and Asian market performance provides cross-border read-through on macro drivers, currency effects, and regional risk appetite.</div>
    <div class="table-wrap" style="margin-bottom:26px;">
      <table class="gtable">
        <thead><tr><th>Index / Asset</th><th>Close</th><th>WTD</th><th>Status</th></tr></thead>
        <tbody>
          {global_rows_html}
        </tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <div class="sec-label">SECTION 07</div>
    <div class="sec-title">Market Breadth &amp; Participation</div>
    <div class="sec-intro">{render_html_text(breadth_summary)} Equal-weight performance and sector participation help distinguish a broad advance from another narrow mega-cap-led move.</div>
    <div class="data-row">
      {breadth_html}
    </div>
  </div>

  <div class="section">
    <div class="sec-label">SECTION 08</div>
    <div class="sec-title">Investor Takeaway: Positioning Read-Through</div>
    <div class="takeaway">{takeaway_text}</div>
  </div>

  <div class="section">
    <div class="sec-label">SECTION 09</div>
    <div class="sec-title">Looking Ahead: What Could Move Markets</div>
    <div class="ahead-grid" style="margin-bottom:24px;">
      <div class="ahead-cell">
        <div class="ahead-day">Macro Data Watch</div>
        <div class="ahead-ev">{lookahead['macro']}</div>
      </div>
      <div class="ahead-cell">
        <div class="ahead-day">Fed &amp; Rates Path</div>
        <div class="ahead-ev">{lookahead['fed_policy']}</div>
      </div>
      <div class="ahead-cell">
        <div class="ahead-day">Earnings, AI &amp; Guidance</div>
        <div class="ahead-ev">{lookahead['earnings_and_catalysts']}</div>
      </div>
      <div class="ahead-cell">
        <div class="ahead-day">Risk Dashboard</div>
        <div class="ahead-ev">{lookahead['risk_factors']}</div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="sec-label">SECTION 10</div>
    <div class="sec-title">S&amp;P 500 &mdash; Hourly Week View {week_start_str}&ndash;{today_str}, {year_str}</div>
    <div class="chart-wrap">
      <div class="chart-hdr">
        <div class="chart-lbl">S&amp;P 500 (SPX) &bull; Hourly Prices Across the Week</div>
        <div class="chart-lbl">Live Data via yfinance &bull; AI Analysis via Claude</div>
      </div>
      <div class="chart-area">
        <canvas id="spxChart" class="chart-canvas" height="280"></canvas>
      </div>
    </div>
  </div>
</div>

<div class="footer">
  <div>Automated Weekly Market Summary &bull; Post-Market Close Edition</div>
  <div>Live Data via yfinance &bull; Narrative Mode: {"Claude" if ai_enabled else "Deterministic Fallback"} &bull; {full_date}</div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
  const labels = {json.dumps(sp_dates)};
  const prices = {json.dumps(sp_data)};
  const root = document.documentElement;

  function getCssVar(name) {{
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }}

  function dedupeMegaCapRows() {{
    const seen = new Set();
    document.querySelectorAll('.co-list .co-row').forEach((row) => {{
      const ticker = row.dataset.ticker || row.querySelector('.tkr')?.textContent?.trim();
      if (!ticker) return;
      if (seen.has(ticker)) {{
        row.remove();
        return;
      }}
      seen.add(ticker);
    }});
  }}

  dedupeMegaCapRows();

  const ctx = document.getElementById('spxChart').getContext('2d');
  let spxChart;

  function buildGradient(context, chartArea) {{
    const gradient = context.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    gradient.addColorStop(0, getCssVar('--chart-fill-top'));
    gradient.addColorStop(1, getCssVar('--chart-fill-bottom'));
    return gradient;
  }}

  function drawCanvasFallback() {{
    if (!prices.length) return;
    const canvas = ctx.canvas;
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || canvas.parentElement.clientWidth || 800;
    const height = canvas.clientHeight || 280;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const pad = 16;
    const xStep = (width - pad * 2) / Math.max(prices.length - 1, 1);
    const yFor = (price) => height - pad - ((price - min) / range) * (height - pad * 2);

    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    for (let i = 1; i < prices.length; i++) {{
      ctx.beginPath();
      ctx.strokeStyle = prices[i] >= prices[i - 1] ? getCssVar('--green') : getCssVar('--red');
      ctx.moveTo(pad + (i - 1) * xStep, yFor(prices[i - 1]));
      ctx.lineTo(pad + i * xStep, yFor(prices[i]));
      ctx.stroke();
    }}
  }}

  function renderChart() {{
    const textColor  = getCssVar('--text');
    const textMuted  = getCssVar('--muted');
    const isLight    = document.documentElement.classList.contains('light');
    const border     = getCssVar('--chart-grid');
    const upColor    = getCssVar('--green');
    const downColor  = getCssVar('--red');
    const pointBorder= getCssVar('--accent');
    const pointBg    = getCssVar('--chart-point-bg');

    if (typeof Chart === 'undefined') {{
      drawCanvasFallback();
      return;
    }}

    if (spxChart) spxChart.destroy();

    spxChart = new Chart(ctx, {{
      type: 'line',
      data: {{
        labels,
        datasets: [{{
          label: 'S&P 500 Hourly',
          data: prices,
          borderColor: upColor,
          segment: {{
            borderColor: ctx => ctx.p1.parsed.y >= ctx.p0.parsed.y ? upColor : downColor
          }},
          backgroundColor: (context) => {{
            const chart = context.chart;
            const {{ ctx: c, chartArea }} = chart;
            if (!chartArea) return getCssVar('--transparent');
            return buildGradient(c, chartArea);
          }},
          fill: true,
          tension: 0.25,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointBackgroundColor: pointBg,
          pointBorderColor: pointBorder,
          pointBorderWidth: 2
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            mode: 'index',
            intersect: false,
            backgroundColor: isLight ? 'rgba(255,255,255,0.85)' : 'rgba(10,10,20,0.85)',
            titleColor: textColor,
            bodyColor: textColor,
            borderColor: getCssVar('--border'),
            borderWidth: 1
          }}
        }},
        scales: {{
          x: {{
            grid: {{ color: border, drawBorder: false }},
            ticks: {{ color: textMuted, maxRotation: 0, autoSkip: true, maxTicksLimit: 7, font: {{ size: 10, weight: '600' }} }}
          }},
          y: {{
            grid: {{ color: border, drawBorder: false }},
            ticks: {{ color: textMuted, font: {{ size: 11, weight: '600' }},
              callback: v => v.toLocaleString() }}
          }}
        }}
      }}
    }});
  }}

  function toggleTheme() {{
    document.documentElement.classList.toggle('light');
    const isLight = document.documentElement.classList.contains('light');
    document.querySelector('.theme-btn').innerHTML = isLight ? '&#x2600;&#xFE0F;' : '&#x1F317;';
    renderChart();
  }}

  renderChart();
</script>
</body>
</html>"""

    html_content = dedupe_tradingview_widget_sections(html_content)

    snapshot = {
        "generated_at": current_market_now().isoformat(),
        "report_mode": "ai" if ai_enabled else "deterministic_fallback",
        "report_window": {
            "start_date": report_start.isoformat(),
            "end_date": report_end.isoformat(),
            "comparison_start": previous_week_end.isoformat(),
            "comparison_end": week_end.isoformat(),
        },
        "market_data": datasets,
        "sector_performance": sector_perf,
        "top_sectors": top_sectors,
        "bottom_sectors": bottom_sectors,
        "market_breadth": {
            "advances": advances,
            "declines": declines,
            "positive_sector_share": breadth_share,
            "spy_pct_change": spy["pct_change"] if not spy.get("error") else None,
            "rsp_pct_change": rspy["pct_change"] if not rspy.get("error") else None,
        },
        "narrative": {
            "sector_bullets": sector_bullets,
            "megacap_descriptions": mc_descriptions,
            "global_status": global_status,
            "crypto_descriptions": crypto_descriptions,
            "takeaway_text": takeaway_text,
            "lookahead": lookahead,
        },
    }

    os.makedirs('public', exist_ok=True)
    with open('public/legacy-report.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    with open('report_snapshot.json', 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2)
    print(f"Successfully generated report_snapshot.json and public/legacy-report.html for {full_date}")


if __name__ == "__main__":
    generate_html()
