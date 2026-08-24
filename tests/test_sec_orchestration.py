import unittest

from earnings_monitor.pipeline import EarningsPipeline
from earnings_monitor.sec_orchestration import (
    make_dilution_lookup,
    make_insider_lookup,
)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0000320193.json"
RAW_TICKERS = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
TICKER_MAP = {"AAPL": RAW_TICKERS["0"]}


def _submissions(rows):
    return {"filings": {"recent": {
        "form": [form for form, _date in rows],
        "filingDate": [_date for _form, _date in rows],
        "accessionNumber": ["0000001-01"] * len(rows),
        "primaryDocument": ["doc.xml"] * len(rows),
    }}}


class FakeSecClient:
    def __init__(self, responses):
        self._responses = responses

    def get_json(self, url):
        if url not in self._responses:
            raise AssertionError(f"unexpected URL: {url}")
        return self._responses[url]


class _Static:
    def __init__(self, payload=None):
        self.payload = payload

    def get(self, *args, **kwargs):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _pipeline_responses():
    return {
        TICKERS_URL: RAW_TICKERS,
        SUBMISSIONS_URL: _submissions([
            ("10-K", "2026-08-01"),
            ("424B5", "2026-08-03"),
        ]),
    }


class SecOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeSecClient(_pipeline_responses())

    def test_insider_lookup_reports_no_recent_filing(self):
        lookup = make_insider_lookup(self.client, ticker_map=TICKER_MAP)
        status = lookup("NASDAQ:AAPL", "2026-08-13T09:30:00+00:00")
        self.assertEqual(status, "NO_RECENT_FILING_FOUND")

    def test_dilution_lookup_detects_recent_424b5(self):
        lookup = make_dilution_lookup(self.client, ticker_map=TICKER_MAP)
        status = lookup("NASDAQ:AAPL", "2026-08-13T09:30:00+00:00")
        self.assertEqual(status, "CONFIRMED_DILUTION")

    def test_unknown_symbol_maps_to_unknown_status(self):
        lookup = make_dilution_lookup(self.client, ticker_map=TICKER_MAP)
        self.assertEqual(lookup("NASDAQ:NOPE", "2026-08-13"), "UNKNOWN")

    def test_lookups_wire_into_pipeline_candidate(self):
        candidate_sources = {}

        class Calendar:
            def get(self, *, symbols, date_from=None, date_to=None):
                return {"status": "PASS", "events": [{
                    "symbol": symbols[0],
                    "next_earnings_date": "2026-09-30",
                    "timing": "time-pre-market",
                }]}

        pipeline = EarningsPipeline(
            calendar=Calendar(),
            quotes=_Static({"status": "PASS", "quotes": {"NASDAQ:AAPL": {"price": 100.0}}}),
            forecasts=_Static({"status": "PASS", "forecast": {
                "eps_estimate": 1.0, "target_upside_pct": 31.0,
                "target_recently_cut": False,
            }}),
            technicals=_Static({"status": "PASS", "values": {
                "price_1d": 98.0, "price_4h": 99.0, "ema20_1d": 99.0,
                "ema20_4h": 100.0, "ema50_1d": 100.0,
                "rsi_1d": 39.0, "adx_1d": 24.0,
            }}),
            news=_Static({"status": "PASS", "negative_news": False}),
            short_interest=_Static({"status": "UNKNOWN"}),
            insider=make_insider_lookup(self.client, ticker_map=TICKER_MAP),
            dilution=make_dilution_lookup(self.client, ticker_map=TICKER_MAP),
        )
        result = pipeline.run(["NASDAQ:AAPL"], as_of="2026-08-13T09:30:00+00:00")
        candidate = result["candidates"][0]
        candidate_sources.update(candidate["sources"])
        self.assertEqual(
            candidate_sources["insider_status"], "NO_RECENT_FILING_FOUND"
        )
        self.assertEqual(
            candidate_sources["dilution_status"], "CONFIRMED_DILUTION"
        )
        news_sec = candidate["score"]["categories"]["news_and_sec"]
        self.assertEqual(news_sec["points"], 2)
        self.assertEqual(news_sec["state"], "PASS")


if __name__ == "__main__":
    unittest.main()

      
