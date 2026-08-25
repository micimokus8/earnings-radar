import json
import unittest

from earnings_monitor.tvremix_news_client import TvremixNewsClient


def mcp_payload(payload):
    return {"result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}


class TvremixNewsClientTests(unittest.TestCase):
    def test_calls_verified_news_tool(self):
        calls = []

        class Session:
            def call_tool(self, name, arguments):
                calls.append((name, arguments))
                return {"status": "PASS", "response": mcp_payload({
                    "success": True,
                    "data": {"count": 0, "headlines": []},
                })}

        result = TvremixNewsClient(Session(), limit=7).get("NASDAQ:AAPL")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["headlines"], [])
        self.assertEqual(calls, [("get_news", {"symbol": "NASDAQ:AAPL", "limit": 7})])

    def test_failed_call_is_unknown(self):
        class Session:
            def call_tool(self, name, arguments):
                return {"status": "UNKNOWN", "response": None, "error": "request_failed"}

        result = TvremixNewsClient(Session()).get("NASDAQ:AAPL")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_evaluates_negative_news_within_window(self):
        class Session:
            def call_tool(self, name, arguments):
                return {"status": "PASS", "response": mcp_payload({
                    "success": True,
                    "data": {"count": 1, "headlines": [
                        {"title": "Company faces lawsuit over accounting",
                         "published": "2026-08-24T12:00:00Z"},
                    ]},
                })}

        result = TvremixNewsClient(Session()).get(
            "NASDAQ:AAPL", as_of="2026-08-25T14:30:00+00:00"
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["negative_news"])
        self.assertTrue(result["matches"])

    def test_clean_headlines_yield_no_negative_news(self):
        class Session:
            def call_tool(self, name, arguments):
                return {"status": "PASS", "response": mcp_payload({
                    "success": True,
                    "data": {"count": 1, "headlines": [
                        {"title": "Company beats estimates, raises guidance",
                         "published": "2026-08-24T12:00:00Z"},
                    ]},
                })}

        result = TvremixNewsClient(Session()).get(
            "NASDAQ:AAPL", as_of="2026-08-25T14:30:00+00:00"
        )
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["negative_news"])
        self.assertEqual(result["matches"], [])

    def test_missing_as_of_treats_as_no_negative_observed(self):
        class Session:
            def call_tool(self, name, arguments):
                return {"status": "PASS", "response": mcp_payload({
                    "success": True,
                    "data": {"count": 1, "headlines": [
                        {"title": "Company faces lawsuit",
                         "published": "2026-08-24T12:00:00Z"},
                    ]},
                })}

        result = TvremixNewsClient(Session()).get("NASDAQ:AAPL")
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["negative_news"])


if __name__ == "__main__":
    unittest.main()

