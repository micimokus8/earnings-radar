import unittest

from earnings_monitor.tvremix_calendar import parse_tvremix_calendar_response


class TvremixCalendarTests(unittest.TestCase):
    def test_parses_data_array(self):
        response = {
            "data": [{
                "symbol": "AAPL",
                "next_earnings_date": "2026-08-12",
                "eps_estimate": 1.5,
                "revenue_estimate": 1000000,
            }]
        }
        result = parse_tvremix_calendar_response(response)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["events"][0]["symbol"], "AAPL")

    def test_parses_results_array(self):
        result = parse_tvremix_calendar_response({"results": [{"symbol": "NVDA"}]})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["events"][0]["symbol"], "NVDA")

    def test_missing_response_is_unknown(self):
        result = parse_tvremix_calendar_response(None)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["events"], [])

    def test_malformed_response_is_unknown(self):
        result = parse_tvremix_calendar_response({"data": {"symbol": "AAPL"}})
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["events"], [])


if __name__ == "__main__":
    unittest.main()
