import unittest

from earnings_monitor.earnings_calendar import normalize_earnings_calendar
from earnings_monitor.tvremix_calendar import parse_tvremix_calendar_response


class CalendarPipelineTests(unittest.TestCase):
    def test_tvremix_response_flows_into_normalized_candidate(self):
        raw = {"data": [{"symbol": "AAPL", "next_earnings_date": "2026-08-12", "eps_estimate": 1.5}]}
        parsed = parse_tvremix_calendar_response(raw)
        result = normalize_earnings_calendar(parsed["events"], timing_by_symbol={"AAPL": "time-after-hours"})
        self.assertEqual(result[0]["status"], "PASS")
        self.assertEqual(result[0]["earnings_timing"], "AFTER_CLOSE")

    def test_unknown_timing_survives_pipeline(self):
        raw = {"data": [{"symbol": "NVDA", "next_earnings_date": "2026-08-12"}]}
        parsed = parse_tvremix_calendar_response(raw)
        result = normalize_earnings_calendar(parsed["events"], timing_by_symbol={})
        self.assertEqual(result[0]["status"], "PARTIAL")
        self.assertEqual(result[0]["earnings_timing"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
