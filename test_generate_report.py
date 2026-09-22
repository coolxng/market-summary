import datetime
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=None))

import generate_report
import offline_fixtures


class FakeColumn:
    def __init__(self, values):
        self.values = values
        self.iloc = self

    def __getitem__(self, position):
        return self.values[position]


class FakeHistory:
    def __init__(self, index, rows):
        self.index = index
        self.rows = rows
        self.iloc = self

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.rows[key]
        return FakeColumn([row[key] for row in self.rows])

    def dropna(self, subset=None):
        return self


def valid_dataset(symbol, session_date, previous_session_date):
    prices = {
        "^GSPC": 6000.0,
        "^IXIC": 19000.0,
        "^DJI": 42000.0,
        "^RUT": 2100.0,
        "^VIX": 20.0,
        "^TNX": 4.2,
        "^IRX": 4.0,
        "DX-Y.NYB": 102.0,
        "GC=F": 2400.0,
        "CL=F": 75.0,
        "BTC-USD": 70000.0,
        "ETH-USD": 3500.0,
        "SOL-USD": 160.0,
        "XRP-USD": 0.75,
        "^N225": 41000.0,
        "^STOXX50E": 5200.0,
        "^FTSE": 8500.0,
        "^HSI": 22000.0,
    }
    end_price = prices.get(symbol, 100.0)
    prev_close = round(end_price / 1.01, 2)
    return {
        "dates": [previous_session_date.isoformat(), session_date.isoformat()],
        "closes": [prev_close, end_price],
        "end_price": end_price,
        "pct_change": round(((end_price - prev_close) / prev_close) * 100, 2),
        "abs_change": round(end_price - prev_close, 2),
        "prev_close": prev_close,
        "session_open": round(prev_close * 1.002, 2),
        "day_high": round(end_price * 1.002, 2),
        "day_low": round(prev_close * 0.998, 2),
        "session_date": session_date.isoformat(),
        "previous_session_date": previous_session_date.isoformat(),
        "ticker_used": symbol,
        "error": None,
    }


class GenerateReportTests(unittest.TestCase):
    def test_normal_tuesday_after_close_selects_tuesday(self):
        now = datetime.datetime(2026, 7, 14, 17, 30, tzinfo=generate_report.NY_TZ)
        session, previous = generate_report.resolve_completed_sessions(
            now,
            session_dates=[datetime.date(2026, 7, 10), datetime.date(2026, 7, 13), datetime.date(2026, 7, 14)],
        )
        self.assertEqual(session, datetime.date(2026, 7, 14))
        self.assertEqual(previous, datetime.date(2026, 7, 13))

    def test_monday_after_close_compares_with_friday(self):
        now = datetime.datetime(2026, 7, 13, 17, 30, tzinfo=generate_report.NY_TZ)
        session, previous = generate_report.resolve_completed_sessions(
            now,
            session_dates=[datetime.date(2026, 7, 9), datetime.date(2026, 7, 10), datetime.date(2026, 7, 13)],
        )
        self.assertEqual(session, datetime.date(2026, 7, 13))
        self.assertEqual(previous, datetime.date(2026, 7, 10))

    def test_weekend_execution_uses_friday(self):
        now = datetime.datetime(2026, 7, 18, 12, 0, tzinfo=generate_report.NY_TZ)
        self.assertEqual(generate_report.latest_completed_session_candidate(now), datetime.date(2026, 7, 17))

    def test_holiday_or_missing_session_uses_latest_available_bar(self):
        now = datetime.datetime(2026, 7, 3, 17, 30, tzinfo=generate_report.NY_TZ)
        session, previous = generate_report.resolve_completed_sessions(
            now,
            session_dates=[datetime.date(2026, 7, 1), datetime.date(2026, 7, 2)],
        )
        self.assertEqual(session, datetime.date(2026, 7, 2))
        self.assertEqual(previous, datetime.date(2026, 7, 1))

    def test_pre_close_run_uses_previous_completed_session(self):
        now = datetime.datetime(2026, 7, 14, 15, 59, tzinfo=generate_report.NY_TZ)
        self.assertEqual(generate_report.latest_completed_session_candidate(now), datetime.date(2026, 7, 13))

    def test_session_calendar_uses_stooq_when_yahoo_fails(self):
        csv_payload = (
            "Date,Open,High,Low,Close,Volume\n"
            "2026-07-10,6200,6220,6180,6210,0\n"
            "2026-07-13,6215,6250,6205,6240,0\n"
            "2026-07-14,6240,6280,6230,6275,0\n"
        )

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return csv_payload.encode("utf-8")

        with (
            mock.patch.object(generate_report.yf, "Ticker", side_effect=RuntimeError("Yahoo unavailable")),
            mock.patch.object(generate_report.urllib.request, "urlopen", return_value=FakeResponse()) as stooq_request,
        ):
            dates = generate_report.fetch_recent_session_dates(datetime.date(2026, 7, 14))

        self.assertEqual(
            dates,
            [datetime.date(2026, 7, 10), datetime.date(2026, 7, 13), datetime.date(2026, 7, 14)],
        )
        request = stooq_request.call_args.args[0]
        self.assertIn("stooq.com/q/d/l/", request.full_url)
        self.assertIn("s=%5Espx", request.full_url)

    def test_vix_stooq_symbol_uses_stooq_vix_code(self):
        self.assertEqual(generate_report.STOOQ_SYMBOLS["^VIX"], "vi.c")

    def test_dst_and_standard_time_are_converted_to_new_york(self):
        utc = datetime.timezone.utc
        summer = datetime.datetime(2026, 7, 14, 21, 30, tzinfo=utc)
        winter = datetime.datetime(2026, 1, 13, 21, 30, tzinfo=utc)
        self.assertEqual(generate_report.latest_completed_session_candidate(summer), datetime.date(2026, 7, 14))
        self.assertEqual(generate_report.latest_completed_session_candidate(winter), datetime.date(2026, 1, 13))

    def test_daily_change_uses_immediately_preceding_session_close(self):
        history = FakeHistory(
            [datetime.date(2026, 7, 10), datetime.date(2026, 7, 13), datetime.date(2026, 7, 14)],
            [
                {"Open": 99.0, "High": 101.0, "Low": 98.0, "Close": 100.0},
                {"Open": 102.0, "High": 104.0, "Low": 101.0, "Close": 103.0},
                {"Open": 104.0, "High": 106.0, "Low": 103.0, "Close": 105.0},
            ],
        )
        ticker = types.SimpleNamespace(history=lambda **kwargs: history)
        with mock.patch.object(generate_report.yf, "Ticker", return_value=ticker):
            result = generate_report.fetch_daily_data(
                "TEST",
                datetime.date(2026, 7, 14),
                datetime.date(2026, 7, 13),
            )
        self.assertEqual(result["prev_close"], 103.0)
        self.assertEqual(result["end_price"], 105.0)
        self.assertEqual(result["pct_change"], 1.94)
        self.assertEqual(result["day_high"], 106.0)
        self.assertEqual(result["day_low"], 103.0)

    def test_fetch_daily_data_uses_stooq_after_yfinance_failure(self):
        csv_payload = (
            "Date,Open,High,Low,Close,Volume\n"
            "2026-07-13,6200,6220,6180,6210,0\n"
            "2026-07-14,6215,6250,6205,6240,0\n"
        )

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return csv_payload.encode("utf-8")

        with (
            mock.patch.object(generate_report.yf, "Ticker", side_effect=RuntimeError("Yahoo unavailable")),
            mock.patch.object(generate_report.urllib.request, "urlopen", return_value=FakeResponse()) as stooq_request,
        ):
            result = generate_report.fetch_daily_data(
                "^GSPC",
                datetime.date(2026, 7, 14),
                datetime.date(2026, 7, 13),
            )

        self.assertEqual(result["end_price"], 6240.0)
        self.assertEqual(result["prev_close"], 6210.0)
        self.assertEqual(result["session_date"], "2026-07-14")
        self.assertEqual(result["previous_session_date"], "2026-07-13")
        self.assertEqual(result["data_source"], "stooq")
        self.assertEqual(result["source_symbol"], "^spx")
        self.assertIsNone(result["error"])
        request = stooq_request.call_args.args[0]
        self.assertIn("stooq.com/q/d/l/", request.full_url)
        self.assertIn("s=%5Espx", request.full_url)

    def test_session_chart_excludes_premarket_and_after_hours(self):
        times = [
            datetime.datetime(2026, 7, 14, 9, 0, tzinfo=generate_report.NY_TZ),
            datetime.datetime(2026, 7, 14, 9, 30, tzinfo=generate_report.NY_TZ),
            datetime.datetime(2026, 7, 14, 12, 0, tzinfo=generate_report.NY_TZ),
            datetime.datetime(2026, 7, 14, 16, 0, tzinfo=generate_report.NY_TZ),
            datetime.datetime(2026, 7, 14, 16, 30, tzinfo=generate_report.NY_TZ),
        ]
        history = FakeHistory(times, [{"Close": value} for value in (99, 100, 102, 103, 104)])
        ticker = types.SimpleNamespace(history=lambda **kwargs: history)
        with mock.patch.object(generate_report.yf, "Ticker", return_value=ticker):
            chart = generate_report.fetch_daily_chart_data("^GSPC", datetime.date(2026, 7, 14))
        self.assertEqual(chart["closes"], [100.0, 102.0, 103.0])
        self.assertEqual(chart["times"], ["9:30 AM", "12:00 PM", "4:00 PM"])
        self.assertEqual(chart["source"], "intraday_5m")
        self.assertEqual(chart["time_zone"], "America/New_York")
        self.assertEqual(chart["timestamps"][0], int(datetime.datetime(2026, 7, 14, 9, 30, tzinfo=generate_report.NY_TZ).timestamp()))

    def test_full_day_chart_preserves_source_market_timezone(self):
        tokyo = datetime.timezone(datetime.timedelta(hours=9))
        times = [
            datetime.datetime(2026, 7, 14, 9, 0, tzinfo=tokyo),
            datetime.datetime(2026, 7, 14, 10, 30, tzinfo=tokyo),
            datetime.datetime(2026, 7, 14, 12, 30, tzinfo=tokyo),
            datetime.datetime(2026, 7, 14, 15, 0, tzinfo=tokyo),
            datetime.datetime(2026, 7, 15, 9, 0, tzinfo=tokyo),
        ]
        history = FakeHistory(times, [{"Close": value} for value in (100, 101, 99, 103, 104)])
        ticker = types.SimpleNamespace(history=lambda **kwargs: history)
        with mock.patch.object(generate_report.yf, "Ticker", return_value=ticker):
            chart = generate_report.fetch_daily_chart_data(
                "^N225",
                datetime.date(2026, 7, 14),
                regular_hours=False,
                prefer_multi_day_fallback=True,
            )
        self.assertEqual(chart["closes"], [100.0, 101.0, 99.0, 103.0])
        self.assertEqual(chart["times"], ["9:00 AM", "10:30 AM", "12:30 PM", "3:00 PM"])
        self.assertEqual(chart["source"], "intraday_5m")

    def test_nikkei_sanity_bound_accepts_current_index_levels(self):
        self.assertTrue(generate_report.is_sane("^N225", 64141.12))

    def test_validate_dataset_rejects_zeroed_core_data(self):
        with self.assertRaisesRegex(ValueError, "end price is invalid"):
            generate_report.validate_dataset(
                {"end_price": 0.0, "closes": [0.0], "ticker_used": "^GSPC", "error": None},
                "^GSPC",
            )

    def test_generated_daily_schema_and_session_dates_agree(self):
        session = datetime.date(2026, 7, 14)
        previous = datetime.date(2026, 7, 13)

        def fake_fetch(symbol, session_date, previous_session_date=None):
            return valid_dataset(symbol, session_date, previous_session_date or previous)

        def fake_chart(
            symbol,
            session_date,
            fallback_data=None,
            *,
            regular_hours=True,
            prefer_multi_day_fallback=False,
        ):
            return {
                "times": ["9:30 AM", "12:00 PM", "4:00 PM"],
                "closes": [fallback_data["session_open"], fallback_data["day_high"], fallback_data["end_price"]],
                "source": "intraday_5m",
                "session_date": session_date.isoformat(),
                "error": None,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "report_snapshot.json"
            archive_root = Path(temp_dir) / "reports"
            with (
                mock.patch.object(generate_report, "resolve_completed_sessions", return_value=(session, previous)),
                mock.patch.object(generate_report, "fetch_daily_data", side_effect=fake_fetch),
                mock.patch.object(generate_report, "fetch_daily_chart_data", side_effect=fake_chart),
                mock.patch.object(generate_report, "should_use_ai", return_value=False),
                offline_fixtures.offline_generation(generate_report),
            ):
                changed = generate_report.generate_html(
                    now=datetime.datetime(2026, 7, 14, 17, 30, tzinfo=generate_report.NY_TZ),
                    snapshot_path=snapshot_path,
                    archive_root=archive_root,
                )

            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            archived_snapshot = json.loads((archive_root / session.isoformat() / "report.json").read_text(encoding="utf-8"))
            self.assertTrue(changed)
            self.assertEqual(snapshot["report_type"], "daily_market_close")
            self.assertEqual(snapshot["session_date"], "2026-07-14")
            self.assertEqual(snapshot["previous_session_date"], "2026-07-13")
            self.assertEqual(snapshot["market_data"]["^GSPC"]["session_date"], snapshot["session_date"])
            self.assertGreater(snapshot["market_data"]["^GSPC"]["end_price"], 0)
            self.assertIn("daily_sector_performance", snapshot)
            self.assertIn("daily_market_breadth", snapshot)
            self.assertEqual(snapshot["mega_cap_data"]["NVDA"]["name"], "Nvidia")
            self.assertGreater(snapshot["mega_cap_data"]["NVDA"]["result"]["end_price"], 0)
            self.assertEqual(snapshot["mega_cap_data"]["NVDA"]["session_chart"]["source"], "intraday_5m")
            self.assertEqual(len(snapshot["mega_cap_data"]["NVDA"]["session_chart"]["closes"]), 3)
            for symbol in ("BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "^N225", "^STOXX50E", "^FTSE", "^HSI"):
                self.assertIn(symbol, snapshot["session_charts"])
                self.assertEqual(len(snapshot["session_charts"][symbol]["closes"]), 3)
            self.assertNotIn("report_window", snapshot)
            self.assertNotIn("hourly_charts", snapshot)
            self.assertIn("asset_history", snapshot)
            self.assertNotIn("asset_history", archived_snapshot)
            self.assertEqual(archived_snapshot, generate_report.archive_snapshot(snapshot))
            self.assertEqual(snapshot["sector_data"]["XLK"]["session_date"], "2026-07-14")

    def test_same_session_does_not_overwrite_artifacts(self):
        session = datetime.date(2026, 7, 14)
        previous = datetime.date(2026, 7, 13)
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "report_snapshot.json"
            archive_root = Path(temp_dir) / "reports"
            snapshot_path.write_text(json.dumps({"report_type": "daily_market_close", "session_date": session.isoformat()}), encoding="utf-8")
            with (
                mock.patch.object(generate_report, "resolve_completed_sessions", return_value=(session, previous)),
                mock.patch.object(generate_report, "fetch_daily_data") as fetch_mock,
            ):
                changed = generate_report.generate_html(snapshot_path=snapshot_path, archive_root=archive_root)
            self.assertFalse(changed)
            fetch_mock.assert_not_called()
            self.assertFalse(archive_root.exists())



class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.session = datetime.date(2026, 7, 14)
        self.previous = datetime.date(2026, 7, 13)
        symbols = ('^GSPC', '^IXIC', '^RUT', '^VIX', '^TNX', '^IRX', 'DX-Y.NYB',
                   'GC=F', 'CL=F', 'BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD',
                   '^N225', '^STOXX50E', '^FTSE', '^HSI')
        self.market = {s: valid_dataset(s, self.session, self.previous) for s in symbols}
        self.market['^GSPC']['pct_change'] = 1
        self.market['^IXIC']['pct_change'] = 1.5
        self.market['^VIX']['pct_change'] = -3
        self.market['^TNX'].update(end_price=4.2, prev_close=4.1)
        self.sectors = {s: valid_dataset(s,self.session,self.previous) for s in ('Tech','Energy','Utilities','Health')}
        self.stocks = {s:{'result':valid_dataset(s,self.session,self.previous)} for s in ('NVDA','AAPL')}
        self.spy = valid_dataset('SPY',self.session,self.previous)
        self.rsp = valid_dataset('RSP',self.session,self.previous)
        self.spy['pct_change']=1;self.rsp['pct_change']=.4
        self.charts={'^GSPC':{'source':'intraday_5m','session_date':self.session.isoformat(),
                             'closes':[100,102,101],'error':None}}

    def context(self):
        return generate_report.build_editorial_context(self.market,self.sectors,self.stocks,
                                                       self.charts,self.spy,self.rsp,self.session)

    def response(self, text, stop_reason='end_turn', content=None):
        response=mock.MagicMock()
        body={'stop_reason':stop_reason,'content':content if content is not None else [{'type':'text','text':text}]}
        response.__enter__.return_value.read.return_value=json.dumps(body).encode()
        return response

    def editorial_response(self, cards, plan=None):
        plan = plan or generate_report.default_editorial_plan(cards)
        return {
            'selection': plan,
            'headline_text': 'Breadth and volatility sharpen the market signal',
            'interpretations': {
                'regime': 'Participation and volatility point to a more coherent risk backdrop.',
                'sector_leadership': 'Relative leadership is clear, while the underlying cause remains unverified.',
                'megacap_leadership': 'Dispersion across the selected leaders keeps the leadership picture selective.',
                'macro_read': 'Rates add valuation pressure without establishing a direct causal link.',
                'investor_takeaway': 'Confirmation across participation and volatility matters more than the headline index alone.',
            },
        }

    def test_derived_metrics_units_and_proxy_limits(self):
        context,cards=self.context();metrics=context['derived_metrics']
        self.assertAlmostEqual(metrics['ten_year_change_bp'],10)
        self.assertEqual(metrics['nasdaq_gap_pp'],.5)
        self.assertAlmostEqual(metrics['equal_weight_minus_cap_weight_pp'],-.6)
        self.assertEqual(metrics['sector_breadth']['positive_share_pct'],100)
        self.assertEqual(metrics['risk_confirmation']['signal'],'risk_on_confirmed')
        self.assertEqual(metrics['intraday']['^GSPC']['close_location_pct'],50)
        self.assertIn('not index contribution',metrics['megacap_sample']['limitation'])
        self.assertIn('not a measured attribution',cards['weighting']['interpretation'])

    def test_missing_stale_and_nonfinite_observations_are_not_zero(self):
        self.rsp['error']='missing'
        self.market['GC=F']['session_date']='2026-07-10'
        self.market['BTC-USD']['pct_change']=float('nan')
        self.stocks['NVDA']['result']['error']='missing'
        self.sectors['Tech']['previous_session_date']='2026-07-09'
        context,cards=self.context()
        self.assertIsNone(context['market']['RSP'])
        self.assertIsNone(context['market']['GC=F'])
        self.assertIsNone(context['market']['BTC-USD'])
        self.assertNotIn('weighting',cards)
        self.assertNotIn('dollar_gold',cards)
        self.assertNotIn('stock_NVDA',cards)
        self.assertEqual(context['derived_metrics']['sector_breadth']['valid'],3)
        json.dumps(context,allow_nan=False)

    def test_proxy_instrument_is_named_without_claiming_futures_price(self):
        self.market['GC=F']['ticker_used']='GLD'
        _,cards=self.context()
        self.assertIn('GLD',cards['dollar_gold']['observed'])
        self.assertNotIn('GC=F',cards['dollar_gold']['observed'])

    def test_daily_fallback_is_not_intraday_evidence(self):
        self.charts['^GSPC']['source']='daily_ohlc_fallback'
        context,cards=self.context()
        self.assertEqual(context['derived_metrics']['intraday'],{})
        self.assertNotIn('intraday',cards)

    def test_tied_sector_and_stock_returns_do_not_invent_winners(self):
        _, cards = self.context()
        self.assertIn('matched', cards['sectors']['observed'])
        self.assertIn('matched', cards['megacaps']['observed'])
        self.assertNotIn('diverge', cards['megacaps']['headline'])

    def test_incomplete_sector_coverage_cannot_confirm_risk_on(self):
        self.sectors['Tech']['error'] = 'unavailable'
        context, _ = self.context()
        self.assertEqual(context['derived_metrics']['risk_confirmation']['signal'], 'mixed')

    def test_flat_range_and_no_positive_stock_returns(self):
        self.charts['^GSPC']['closes']=[100,100,100]
        for stock in self.stocks.values():stock['result']['pct_change']=-1
        context,_=self.context()
        self.assertIsNone(context['derived_metrics']['intraday']['^GSPC']['close_location_pct'])
        self.assertIsNone(context['derived_metrics']['megacap_sample']['leader_share_of_positive_returns_pct'])

    def test_closed_schema_and_successful_single_request(self):
        context,cards=self.context();plan=generate_report.default_editorial_plan(cards)
        plan['headline']=['intraday'];plan['macro_read']=['dollar_gold']
        ai_response=self.editorial_response(cards,plan)
        with mock.patch.object(generate_report,'ANTHROPIC_API_KEY','test-private-key'), mock.patch.object(
                generate_report.urllib.request,'urlopen',return_value=self.response(json.dumps(ai_response))) as send:
            brief,provenance=generate_report.generate_editorial(context,cards)
        send.assert_called_once()
        payload=json.loads(send.call_args.args[0].data)
        self.assertEqual(payload['max_tokens'],1200)
        schema=payload['output_config']['format']
        self.assertEqual(schema['type'],'json_schema')
        self.assertIn('selection',schema['schema']['properties'])
        self.assertIn('headline_text',schema['schema']['properties'])
        self.assertIn('interpretations',schema['schema']['properties'])
        self.assertNotIn('test-private-key',json.dumps(payload))
        self.assertEqual(brief['headline'],ai_response['headline_text'])
        self.assertEqual(brief['regime']['interpretation'],ai_response['interpretations']['regime'])
        self.assertEqual(provenance['mode'],'ai')
        self.assertEqual(provenance['status'],'validated')
        self.assertTrue(provenance['ai_writing'])
        self.assertEqual(provenance['contract_version'],2)
        self.assertNotIn('test-private-key',json.dumps([brief,provenance]))

    def test_ai_prose_rejects_numbers_causes_and_predictions(self):
        _,cards=self.context();valid=self.editorial_response(cards)
        cases=[
            ('headline_text','S&P gains 1 percent'),
            ('regime','Stocks rose because inflation cooled'),
            ('macro_read','Rates will likely support equities'),
        ]
        for field,value in cases:
            with self.subTest(field=field):
                bad=json.loads(json.dumps(valid))
                if field=='headline_text':
                    bad[field]=value
                else:
                    bad['interpretations'][field]=value
                with self.assertRaises(ValueError):
                    generate_report.parse_editorial_response(json.dumps(bad),cards)

    def test_no_key_uses_grounded_fallback_without_network(self):
        context,cards=self.context()
        with mock.patch.object(generate_report,'ANTHROPIC_API_KEY',''), mock.patch.object(generate_report.urllib.request,'urlopen') as send:
            brief,provenance=generate_report.generate_editorial(context,cards)
        send.assert_not_called()
        self.assertEqual(provenance['mode'],'deterministic_fallback')
        self.assertEqual(provenance['status'],'missing_key')
        self.assertTrue(brief['watchlist'])

    def test_parser_rejects_malformed_wrong_types_unknown_and_extra_fields(self):
        _,cards=self.context();valid=generate_report.default_editorial_plan(cards)
        invalid=['not JSON','```json\n'+json.dumps(valid)+'\n```','[]']
        for field,value in [('headline','index'),('headline',[123]),('headline',['invented catalyst']),
                            ('headline',[]),('headline',['index','risk']),
                            ('macro_read',['index']),('watchlist',['risk','risk']),
                            ('watchlist',['risk']*4)]:
            bad=dict(valid);bad[field]=value;invalid.append(json.dumps(bad))
        bad=dict(valid);bad['free_text']='Earnings surprise';invalid.append(json.dumps(bad))
        bad=dict(valid);bad.pop('regime');invalid.append(json.dumps(bad))
        invalid.append(json.dumps(valid)[:-1]+',"headline":["index"]}')
        for raw in invalid:
            with self.subTest(raw=raw):
                with self.assertRaises((ValueError,TypeError)):
                    generate_report.parse_editorial_plan(raw,cards)

    def test_failure_truncation_refusal_and_malformed_output_fall_back(self):
        context,cards=self.context();valid=json.dumps(generate_report.default_editorial_plan(cards))
        responses=[self.response(valid,stop_reason='max_tokens'),self.response(valid,stop_reason='refusal'),
                   self.response('bad JSON'),self.response(valid,content=[{'type':'tool_use'}]),
                   self.response(valid,content=[])]
        for response in responses:
            with self.subTest(response=response),mock.patch.object(generate_report,'ANTHROPIC_API_KEY','private'),mock.patch.object(
                generate_report.urllib.request,'urlopen',return_value=response):
                brief,provenance=generate_report.generate_editorial(context,cards)
                self.assertEqual(provenance['mode'],'deterministic_fallback')
                self.assertTrue(brief['opening_summary'])

    def test_api_exception_does_not_log_secret_or_response(self):
        import io
        context,cards=self.context();logs=io.StringIO()
        with mock.patch.object(generate_report,'ANTHROPIC_API_KEY','private'),mock.patch.object(
                generate_report.urllib.request,'urlopen',side_effect=TimeoutError('secret-value')),mock.patch('sys.stdout',logs):
            _,provenance=generate_report.generate_editorial(context,cards)
        self.assertEqual(provenance['mode'],'deterministic_fallback')
        self.assertNotIn('secret-value',logs.getvalue())

    def test_generation_uses_one_request_preserves_raw_data_and_records_real_status(self):
        session=self.session;previous=self.previous
        def fetch(symbol,*args):return valid_dataset(symbol,session,previous)
        def chart(symbol,day,fallback_data=None,**kwargs):
            return {'source':'daily_ohlc_fallback','session_date':session.isoformat(),
                    'closes':[fallback_data['session_open'],fallback_data['end_price']],
                    'times':['9:30 AM','4:00 PM'],'error':None}
        for succeeds in (True,False):
            with self.subTest(succeeds=succeeds),tempfile.TemporaryDirectory() as tmp:
                def reply(request,**kwargs):
                    payload=json.loads(request.data)
                    supplied=json.loads(payload['messages'][0]['content'])
                    plan=generate_report.default_editorial_plan(supplied['catalog'])
                    ai_response=self.editorial_response(supplied['catalog'],plan)
                    return self.response(json.dumps(ai_response) if succeeds else 'not-json')
                with mock.patch.object(generate_report,'resolve_completed_sessions',return_value=(session,previous)),mock.patch.object(
                        generate_report,'fetch_daily_data',side_effect=fetch),mock.patch.object(generate_report,'fetch_daily_chart_data',side_effect=chart),mock.patch.object(
                        generate_report,'ANTHROPIC_API_KEY','test-private-key'),mock.patch.object(generate_report.urllib.request,'urlopen',side_effect=reply) as send,offline_fixtures.offline_generation(generate_report):
                    archive_root=Path(tmp)/'reports'
                    generate_report.generate_html(snapshot_path=Path(tmp)/'snapshot.json',archive_root=archive_root)
                send.assert_called_once()
                snapshot=json.loads((Path(tmp)/'snapshot.json').read_text())
                archived=json.loads((archive_root/session.isoformat()/'report.json').read_text())
                self.assertEqual(snapshot['market_data']['^GSPC'],fetch('^GSPC'))
                self.assertEqual(snapshot['report_mode'],'ai' if succeeds else 'deterministic_fallback')
                self.assertEqual(archived,generate_report.archive_snapshot(snapshot))
                self.assertNotIn('test-private-key',(Path(tmp)/'snapshot.json').read_text())
                self.assertNotIn('test-private-key',(archive_root/session.isoformat()/'report.json').read_text())

    def test_opening_summary_does_not_repeat_index_move(self):
        cards = {
            'index': {'observed': 'S&P 500 +1.49% at the close.'},
            'risk': {'observed': 'S&P 500 +1.49%; VIX +0.41%; positive sector share 18.2%.'},
        }
        self.assertEqual(
            generate_report.compose_observed(cards, ['index', 'risk']),
            'S&P 500 +1.49% at the close. VIX +0.41%; positive sector share 18.2%.',
        )
        self.assertEqual(generate_report.compose_observed(cards, ['risk']), cards['risk']['observed'])

    def test_empty_optional_groups_are_valid_but_no_fabricated_ids(self):
        _,cards=self.context();cards={k:v for k,v in cards.items() if v['group']!='megacap'}
        plan=generate_report.default_editorial_plan(cards)
        self.assertEqual(plan['megacap_leadership'],[])
        self.assertEqual(generate_report.parse_editorial_plan(json.dumps(plan),cards),plan)
        plan['megacap_leadership']=['unavailable']
        with self.assertRaises(ValueError):generate_report.parse_editorial_plan(json.dumps(plan),cards)


if __name__ == "__main__":
    unittest.main()
