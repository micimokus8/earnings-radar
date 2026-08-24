import unittest

from earnings_monitor.tvremix_quotes_client import TvremixQuotesClient


class TvremixQuotesClientTests(unittest.TestCase):
    def test_calls_batch_quote_tool_and_normalizes(self):
        calls = []

        class Session:
            def call_tool(self, name, arguments):
                calls.append((name, arguments))
                return {
                    "status": "PASS",
                    "response": {"result": {"content": [{"type": "text", "text":
                        '{"success":true,"data":{"NASDAQ:AAPL":{"price":200.5,'
                        '"market_cap":3000000000000,"volume":123456,"change_percent":1.2}}}'
                    }]}},
                }

        result = TvremixQuotesClient(Session()).get(["NASDAQ:AAPL"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["quotes"]["NASDAQ:AAPL"]["price"], 200.5)
        self.assertEqual(calls, [("get_quotes_batch", {"symbols": ["NASDAQ:AAPL"]})])

    def test_session_failure_is_unknown(self):
        class Session:
            def call_tool(self, name, arguments):
                return {"status": "UNKNOWN", "response": None, "error": "request_failed"}

        result = TvremixQuotesClient(Session()).get(["NASDAQ:AAPL"])
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

