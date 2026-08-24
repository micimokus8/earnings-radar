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


if __name__ == "__main__":
    unittest.main()

