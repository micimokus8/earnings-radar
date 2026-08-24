import unittest

from earnings_monitor.sec_dilution import classify_dilution_filings


class DilutionClassificationTests(unittest.TestCase):
    def test_recent_424b5_is_confirmed_dilution(self):
        result = classify_dilution_filings([
            {"form": "424B5", "filed": "2026-08-10"}
        ], as_of="2026-08-12")
        self.assertEqual(result["status"], "CONFIRMED_DILUTION")
        self.assertTrue(result["point_deduction"])

    def test_recent_s3_is_context_not_confirmed_dilution(self):
        result = classify_dilution_filings([
            {"form": "S-3", "filed": "2026-08-01"}
        ], as_of="2026-08-12")
        self.assertEqual(result["status"], "SHELF_ACTIVE")
        self.assertFalse(result["point_deduction"])

    def test_old_424b5_is_ignored(self):
        result = classify_dilution_filings([
            {"form": "424B5", "filed": "2026-06-01"}
        ], as_of="2026-08-12")
        self.assertEqual(result["status"], "NO_DILUTION_FILING_FOUND")

    def test_request_failure_is_unknown_not_no_filing(self):
        result = classify_dilution_filings(None, as_of="2026-08-12")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["point_deduction"])


if __name__ == "__main__":
    unittest.main()
