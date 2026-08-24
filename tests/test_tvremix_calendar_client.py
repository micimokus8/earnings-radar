import unittest

from earnings_monitor.tvremix_calendar_client import TvremixCalendarClient


class TvremixCalendarClientTests(unittest.TestCase):
    def test_calls_verified_calendar_tool_and_normalizes(self):
        calls = []

        class Session:
            def call_tool(self, name, arguments):
                calls.append((name, arguments))
                return {
                    "status": "PASS",
                    "response": {"result": {"content": [{"type": "text", "text":
                        '{"success":true,"data":[{"symbol":"NASDAQ:AAPL",'
                        '"next_earnings_date":"2026-08-20",'
                        '"eps_estimate":1.5,"revenue_estimate":90000000000}]}'
                    }]}},
                }

        result = TvremixCalendarClient(Session()).get(
            symbols=["NASDAQ:AAPL"],
            date_from="2026-08-19",
            date_to="2026-08-21",
        )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["events"][0]["symbol"], "NASDAQ:AAPL")
        self.assertEqual(calls, [(
            "get_earnings_calendar",
            {
                "symbols": ["NASDAQ:AAPL"],
                "market": "america",
                "date_from": "2026-08-19",
                "date_to": "2026-08-21",
                "limit": 50,
            },
        )])

    def test_session_failure_is_unknown(self):
        class Session:
            def call_tool(self, name, arguments):
                return {"status": "UNKNOWN", "response": None, "error": "request_failed"}

        result = TvremixCalendarClient(Session()).get(symbols=["NASDAQ:AAPL"])
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
