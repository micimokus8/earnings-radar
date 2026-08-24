import unittest

from earnings_monitor.candidate import build_candidate


class CandidateTests(unittest.TestCase):
    def test_builds_auditable_candidate_and_blocks_missing_short_interest(self):
        result = build_candidate(
            symbol="NASDAQ:AAPL",
            as_of="2026-08-13T16:00:00+00:00",
            calendar={
                "status": "PASS",
                "earnings_date": "2026-09-30",
                "earnings_timing": "BEFORE_OPEN",
            },
            quote={
                "status": "PASS",
                "quotes": {"NASDAQ:AAPL": {"price": 100.0, "market_cap": 3_000_000_000}},
            },
            forecast={
                "status": "PASS",
                "forecast": {
                    "eps_estimate": 1.0,
                    "target_upside_pct": 31.0,
                    "target_recently_cut": False,
                },
            },
            technicals={
                "status": "PASS",
                "values": {
                    "price_1d": 98.0, "price_4h": 99.0,
                    "ema20_1d": 99.0, "ema20_4h": 100.0,
                    "ema50_1d": 100.0, "rsi_1d": 39.0, "adx_1d": 24.0,
                },
            },
            news={"status": "PASS", "negative_news": False},
            short_interest={"status": "UNKNOWN", "reason": "provider_unavailable"},
            insider_status="NO_RECENT_FILING_FOUND",
            dilution_status="NO_DILUTION_FILING_FOUND",
        )
        self.assertEqual(result["symbol"], "NASDAQ:AAPL")
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["score"]["state"], "INCOMPLETE")
        self.assertIsNone(result["score"]["label"])
        self.assertIn("short_pct_outstanding", result["score"]["missing"])
        self.assertEqual(result["values"]["market_cap"], 3_000_000_000)
        self.assertEqual(result["sources"]["quote"]["status"], "PASS")

    def test_none_forecast_block_does_not_crash(self):
        result = build_candidate(
            symbol="NASDAQ:X",
            as_of="2026-08-24T16:30:00+00:00",
            forecast={"status": "PARTIAL", "forecast": None},
        )
        self.assertIsNone(result["values"]["eps_estimate"])

    def test_missing_symbol_is_incomplete(self):
        result = build_candidate(symbol="", as_of="2026-08-13T16:00:00+00:00")
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIn("symbol", result["missing"])


if __name__ == "__main__":
    unittest.main()

        
