import unittest

from earnings_monitor.short_interest_values import build_short_interest_values


class BuildShortInterestValuesTests(unittest.TestCase):
    def test_combines_nasdaq_row_and_shares_outstanding(self):
        result = build_short_interest_values(
            {
                "status": "PASS",
                "report_date": "2026-07-31",
                "shares_short": 141_606_163,
                "days_to_cover": 2.42,
            },
            shares_outstanding_millions=14_800.0,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["report_date"], "2026-07-31")
        self.assertAlmostEqual(result["short_pct_outstanding"], 0.95680, places=4)
        self.assertEqual(result["days_to_cover"], 2.42)

    def test_unknown_si_stays_unknown(self):
        result = build_short_interest_values(
            {"status": "UNKNOWN", "report_date": None,
             "shares_short": None, "days_to_cover": None},
            shares_outstanding_millions=14_800.0,
        )
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["short_pct_outstanding"])

    def test_pass_without_outstanding_is_partial_with_visible_days(self):
        result = build_short_interest_values(
            {"status": "PASS", "report_date": "2026-07-31",
             "shares_short": 141_606_163, "days_to_cover": 2.42},
            shares_outstanding_millions=None,
        )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIsNone(result["short_pct_outstanding"])
        self.assertEqual(result["days_to_cover"], 2.42)

    def test_invalid_denominator_yields_partial_not_fake_zero(self):
        result = build_short_interest_values(
            {"status": "PASS", "report_date": "2026-07-31",
             "shares_short": 1_000_000, "days_to_cover": 5.0},
            shares_outstanding_millions=0.0,
        )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIsNone(result["short_pct_outstanding"])


if __name__ == "__main__":
    unittest.main()

      
