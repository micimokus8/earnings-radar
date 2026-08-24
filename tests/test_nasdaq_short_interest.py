import unittest

from earnings_monitor.nasdaq_short_interest import parse_nasdaq_short_interest


class NasdaqShortInterestTests(unittest.TestCase):
    def test_parses_newest_row_to_normalized_values(self):
        rows = [
            {"settlementDate": "07/15/2026", "interest": "146,547,784",
             "avgDailyShareVolume": "47,952,794", "daysToCover": 3.056},
            {"settlementDate": "07/31/2026", "interest": "141,606,163",
             "avgDailyShareVolume": "58,400,983", "daysToCover": 2.424722},
        ]
        result = parse_nasdaq_short_interest(
            rows, as_of="2026-08-13T09:30:00+00:00"
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["report_date"], "2026-07-31")
        self.assertEqual(result["shares_short"], 141_606_163)
        self.assertAlmostEqual(result["days_to_cover"], 2.424722)

    def test_stale_when_older_than_max_age_days(self):
        rows = [{
            "settlementDate": "06/30/2026", "interest": "140,000,000",
            "daysToCover": 1.7,
        }]
        result = parse_nasdaq_short_interest(
            rows, as_of="2026-08-20T09:30:00+00:00", max_age_days=45
        )
        self.assertEqual(result["status"], "STALE")
        self.assertEqual(result["report_date"], "2026-06-30")
        self.assertIsNone(result["shares_short"])
        self.assertIsNone(result["days_to_cover"])

    def test_empty_rows_are_unknown(self):
        result = parse_nasdaq_short_interest([], as_of="2026-08-13")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_invalid_values_are_unknown(self):
        rows = [{"settlementDate": "not-a-date", "interest": "x", "daysToCover": None}]
        result = parse_nasdaq_short_interest(rows, as_of="2026-08-13")
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

      
