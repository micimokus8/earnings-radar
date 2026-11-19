import unittest

from earnings_monitor.rules import evaluate_news_sec, evaluate_core_completeness


class RuleStateTests(unittest.TestCase):
    def test_unknown_subcheck_does_not_earn_points(self):
        result = evaluate_news_sec(
            news_status="UNKNOWN",
            negative_news=False,
            insider_status="NO_DIRECT_SELL",
            dilution_status="NO_DILUTION_FILING_FOUND",
        )
        self.assertEqual(result["state"], "PARTIAL")
        self.assertEqual(result["points"], 2)
        self.assertIn("news", result["unknown"])

    def test_successful_no_negative_news_is_not_unknown(self):
        result = evaluate_news_sec(
            news_status="PASS",
            negative_news=False,
            insider_status="NO_DIRECT_SELL",
            dilution_status="NO_DILUTION_FILING_FOUND",
        )
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["points"], 3)

    def test_confirmed_dilution_removes_only_dilution_point(self):
        result = evaluate_news_sec(
            news_status="PASS",
            negative_news=False,
            insider_status="NO_DIRECT_SELL",
            dilution_status="CONFIRMED_DILUTION",
        )
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["points"], 2)

    def test_missing_chart_blocks_final_recommendation(self):
        result = evaluate_core_completeness({
            "price_1d": 100,
            "rsi_1d": None,
            "high_52w": 120,
            "short_pct_outstanding": None,
        })
        self.assertEqual(result["state"], "INCOMPLETE")
        self.assertFalse(result["final_recommendation_allowed"])
        self.assertIn("rsi_1d", result["missing"])
        self.assertNotIn("short_pct_outstanding", result["missing"])

    def test_complete_core_values_allow_final_recommendation(self):
        result = evaluate_core_completeness({
            "price_1d": 100,
            "rsi_1d": 50,
            "high_52w": 120,
        })
        self.assertEqual(result["state"], "COMPLETE")
        self.assertTrue(result["final_recommendation_allowed"])

    def test_unsupported_short_interest_does_not_block_completeness(self):
        result = evaluate_core_completeness({
            "price_1d": 100,
            "rsi_1d": 50,
            "high_52w": 120,
            "short_pct_outstanding": None,
            "days_to_cover": None,
            "short_interest_supported": False,
        })
        self.assertEqual(result["state"], "COMPLETE")
        self.assertTrue(result["final_recommendation_allowed"])
        self.assertNotIn("short_pct_outstanding", result["missing"])


if __name__ == "__main__":
    unittest.main()
