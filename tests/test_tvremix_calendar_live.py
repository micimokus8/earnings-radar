import unittest

from earnings_monitor.tvremix_calendar import parse_tvremix_calendar_response


class TvremixCalendarLiveTests(unittest.TestCase):
    def test_parses_mcp_calendar_envelope(self):
        response = {
            "result": {"content": [{"type": "text", "text":
                '{"success":true,"data":[{"symbol":"NASDAQ:AAPL",'
                '"next_earnings_date":"2026-08-20",'
                '"eps_estimate":1.5,"revenue_estimate":90000000000}]}'
            }]}
        }
        result = parse_tvremix_calendar_response(response)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["events"][0]["symbol"], "NASDAQ:AAPL")
        self.assertEqual(result["events"][0]["eps_estimate"], 1.5)

    def test_parses_mcp_calendar_object_with_earnings(self):
        response = {
            "result": {"content": [{"type": "text", "text":
                '{"success":true,"data":{"count":1,"earnings":[{"symbol":"NASDAQ:MSFT",'
                '"next_earnings_date":"2026-08-21"}]}}'
            }]}
        }
        result = parse_tvremix_calendar_response(response)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["events"][0]["symbol"], "NASDAQ:MSFT")

    def test_invalid_mcp_text_is_unknown(self):
        response = {"result": {"content": [{"type": "text", "text": "bad"}]}}
        result = parse_tvremix_calendar_response(response)
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
