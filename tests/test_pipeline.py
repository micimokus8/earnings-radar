import unittest

from earnings_monitor.pipeline import EarningsPipeline


class _Calendar:
    def get(self, *, symbols, date_from=None, date_to=None):
        return {"status": "PASS", "events": [{
            "symbol": symbols[0],
            "next_earnings_date": "2026-09-30",
            "timing": "time-pre-market",
            "eps_estimate": 1.0,
        }]}


class _Quotes:
    def get(self, symbols):
        return {"status": "PASS", "quotes": {symbols[0]: {"price": 100.0, "market_cap": 3_000_000_000}}}


class _Forecasts:
    def get(self, symbol, *, price):
        return {"status": "PASS", "forecast": {
            "eps_estimate": 1.0,
            "target_upside_pct": 31.0,
            "target_recently_cut": False,
        }}


class _Technicals:
    def get(self, symbol):
        return {"status": "PASS", "values": {
            "price_1d": 98.0, "price_4h": 99.0,
            "ema20_1d": 99.0, "ema20_4h": 100.0,
            "ema50_1d": 100.0, "rsi_1d": 39.0, "adx_1d": 24.0,
        }}


class _News:
    def get(self, symbol):
        return {"status": "PASS", "negative_news": False}


class _ShortInterest:
    def get(self, symbol, *, as_of):
        return {"status": "UNKNOWN", "reason": "provider_unavailable"}


class PipelineTests(unittest.TestCase):
    def test_runs_all_sources_and_returns_incomplete_candidate(self):
        pipeline = EarningsPipeline(
            calendar=_Calendar(), quotes=_Quotes(), forecasts=_Forecasts(),
            technicals=_Technicals(), news=_News(), short_interest=_ShortInterest(),
            insider=lambda symbol, as_of: "NO_RECENT_FILING_FOUND",
            dilution=lambda symbol, as_of: "NO_DILUTION_FILING_FOUND",
        )
        result = pipeline.run(["NASDAQ:AAPL"], as_of="2026-08-13T16:00:00+00:00")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["candidates"]), 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["status"], "INCOMPLETE")
        self.assertIsNone(candidate["score"]["label"])
        self.assertEqual(candidate["sources"]["short_interest"]["status"], "UNKNOWN")

    def test_source_exception_becomes_unknown_candidate_source(self):
        class BrokenNews:
            def get(self, symbol):
                raise RuntimeError("network")

        pipeline = EarningsPipeline(
            calendar=_Calendar(), quotes=_Quotes(), forecasts=_Forecasts(),
            technicals=_Technicals(), news=BrokenNews(), short_interest=_ShortInterest(),
        )
        result = pipeline.run(["NASDAQ:AAPL"], as_of="2026-08-13T16:00:00+00:00")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["candidates"][0]["sources"]["news"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

      
