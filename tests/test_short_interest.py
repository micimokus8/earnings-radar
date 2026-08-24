import unittest

from earnings_monitor.short_interest import normalize_short_interest


class ShortInterestTests(unittest.TestCase):
    def test_converts_float_millions_and_short_shares_to_percent(self):
        result = normalize_short_interest({
            "floatingShare": 100.0,
            "shortQty": 15_000_000,
            "daysToCover": 4.0,
            "reportDate": "2026-08-10",
        }, as_of="2026-08-13", max_age_days=10)
        self.assertEqual(result["status"], "PASS")
        self.assertAlmostEqual(result["short_pct_float"], 15.0)
        self.assertEqual(result["days_to_cover"], 4.0)

    def test_stale_report_is_unknown_not_zero(self):
        result = normalize_short_interest({
            "floatingShare": 100.0,
            "shortQty": 15_000_000,
            "daysToCover": 4.0,
            "reportDate": "2026-07-01",
        }, as_of="2026-08-13", max_age_days=10)
        self.assertEqual(result["status"], "STALE")
        self.assertIsNone(result["short_pct_float"])
        self.assertIsNone(result["days_to_cover"])

    def test_missing_or_implausible_values_are_unknown(self):
        missing = normalize_short_interest({}, as_of="2026-08-13")
        self.assertEqual(missing["status"], "UNKNOWN")
        bad = normalize_short_interest({
            "floatingShare": 0,
            "shortQty": 1,
            "daysToCover": -1,
            "reportDate": "2026-08-13",
        }, as_of="2026-08-13")
        self.assertEqual(bad["status"], "UNKNOWN")
        self.assertIsNone(bad["short_pct_float"])


if __name__ == "__main__":
    unittest.main()

