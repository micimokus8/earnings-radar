import unittest

from earnings_monitor.earnings_calendar import normalize_earnings_calendar


class EarningsCalendarTests(unittest.TestCase):
    def test_normalizes_known_event(self):
        raw = [{"symbol": "AAPL", "next_earnings_date": "2026-08-12", "eps_estimate": 1.5}]
        result = normalize_earnings_calendar(raw, timing_by_symbol={"AAPL": "time-pre-market"})
        self.assertEqual(result[0]["symbol"], "AAPL")
        self.assertEqual(result[0]["earnings_timing"], "BEFORE_OPEN")
        self.assertEqual(result[0]["eps_estimate"], 1.5)
        self.assertEqual(result[0]["status"], "PASS")

    def test_missing_timing_is_unknown_not_after_close(self):
        raw = [{"symbol": "NVDA", "next_earnings_date": "2026-08-12"}]
        result = normalize_earnings_calendar(raw, timing_by_symbol={})
        self.assertEqual(result[0]["earnings_timing"], "UNKNOWN")
        self.assertEqual(result[0]["status"], "PARTIAL")

    def test_missing_symbol_is_incomplete(self):
        raw = [{"next_earnings_date": "2026-08-12"}]
        result = normalize_earnings_calendar(raw, timing_by_symbol={})
        self.assertEqual(result[0]["status"], "INCOMPLETE")
        self.assertIn("symbol", result[0]["missing"])


if __name__ == "__main__":
    unittest.main()