import unittest

from earnings_monitor.scoring import score_candidate


COMPLETE_BASE = {
    "price": 100,
    "eps_estimate": 1.0,
    "ohlcv_1d": "present",
    "market_cap": 3_000_000_000,
    "short_pct_outstanding": 0.0,
    "days_to_cover": 0.0,
    "target_upside_pct": 0.0,
    "target_recently_cut": False,
    "price_1d": 100,
    "ema20_1d": 100,
    "price_4h": 100,
    "ema20_4h": 100,
    "ema50_1d": 100,
    "rsi_1d": 40,
    "adx_1d": 25,
    "news_status": "PASS",
    "negative_news": False,
    "insider_status": "NO_DIRECT_SELL",
    "dilution_status": "NO_DILUTION_FILING_FOUND",
}


class ScoringTests(unittest.TestCase):
    def test_all_positive_rules_total_fourteen_and_strong(self):
        values = {**COMPLETE_BASE,
            "eps_estimate": -0.1,
            "target_upside_pct": 31,
            "target_recently_cut": True,
            "short_pct_outstanding": 16,
            "days_to_cover": 4,
            "price_1d": 98, "ema20_1d": 99,
            "price_4h": 99, "ema20_4h": 100,
            "ema50_1d": 100,
            "rsi_1d": 39, "adx_1d": 24,
        }
        result = score_candidate(values)
        self.assertEqual(result["total_points"], 14)
        self.assertEqual(result["label"], "STRONG_SETUP")
        self.assertEqual(result["state"], "COMPLETE")

    def test_short_thresholds_are_cumulative(self):
        values = {**COMPLETE_BASE, "short_pct_outstanding": 16, "days_to_cover": 4}
        result = score_candidate(values)
        self.assertEqual(result["categories"]["short_interest"]["points"], 3)

    def test_boundary_values_do_not_trigger_strict_greater_rules(self):
        values = {**COMPLETE_BASE, "short_pct_outstanding": 15, "days_to_cover": 3}
        result = score_candidate(values)
        self.assertEqual(result["categories"]["short_interest"]["points"], 1)

    def test_unknown_news_subcheck_is_partial_and_no_point(self):
        values = {**COMPLETE_BASE, "news_status": "UNKNOWN"}
        result = score_candidate(values)
        category = result["categories"]["news_and_sec"]
        self.assertEqual(category["state"], "PARTIAL")
        self.assertEqual(category["points"], 2)

    def test_no_recent_filing_is_successful_insider_check(self):
        values = {**COMPLETE_BASE, "insider_status": "NO_RECENT_FILING_FOUND"}
        result = score_candidate(values)
        self.assertEqual(result["categories"]["news_and_sec"]["points"], 3)
        self.assertEqual(result["categories"]["news_and_sec"]["state"], "PASS")

    def test_confirmed_dilution_does_not_earn_dilution_point(self):
        values = {**COMPLETE_BASE, "dilution_status": "CONFIRMED_DILUTION"}
        result = score_candidate(values)
        self.assertEqual(result["categories"]["news_and_sec"]["points"], 2)

    def test_missing_core_value_blocks_label_and_marks_incomplete(self):
        values = {**COMPLETE_BASE, "days_to_cover": None}
        result = score_candidate(values)
        self.assertEqual(result["state"], "INCOMPLETE")
        self.assertIsNone(result["label"])
        self.assertFalse(result["final_recommendation_allowed"])

    def test_unsupported_short_interest_is_neutral_na(self):
        # Exchange not covered (e.g. NYSE): short-interest is neutrally excluded,
        # not penalized, and must not inject unknown fields.
        values = {**COMPLETE_BASE,
                  "short_pct_outstanding": None,
                  "days_to_cover": None,
                  "short_interest_supported": False}
        result = score_candidate(values)
        category = result["categories"]["short_interest"]
        self.assertEqual(category["state"], "N/A")
        self.assertEqual(category["points"], 0)
        self.assertEqual(category["unknown"], [])
        # Remaining categories still score normally -> candidate is complete.
        self.assertEqual(result["state"], "COMPLETE")
        self.assertIsNotNone(result["label"])


if __name__ == "__main__":
    unittest.main()
