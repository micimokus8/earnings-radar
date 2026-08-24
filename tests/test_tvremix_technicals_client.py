import json
import unittest

from earnings_monitor.tvremix_technicals_client import TvremixTechnicalsClient


def mcp_payload(payload):
    return {"result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}


class TvremixTechnicalsClientTests(unittest.TestCase):
    def test_calls_verified_tools_with_exact_arguments(self):
        calls = []

        class Session:
            def call_tool(self, name, arguments):
                calls.append((name, arguments))
                if name == "get_technicals":
                    return {"status": "PASS", "response": mcp_payload({
                        "success": True,
                        "data": {"price": 100, "oscillators": {"rsi": 39}, "summary": {}},
                    })}
                return {"status": "PASS", "response": mcp_payload({
                    "success": True,
                    "symbol": "NASDAQ:AAPL",
                    "interval": "1D",
                    "bars": [{"t": 1, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}],
                })}

        result = TvremixTechnicalsClient(Session()).get("NASDAQ:AAPL", ohlcv_count=300)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["technicals"]["1D"]["rsi"], 39)
        self.assertEqual(result["technicals"]["4h"]["rsi"], 39)
        self.assertEqual(len(result["ohlcv"]["1D"]["bars"]), 1)
        self.assertEqual(calls, [
            ("get_technicals", {"symbol": "NASDAQ:AAPL", "interval": "1D"}),
            ("get_technicals", {"symbol": "NASDAQ:AAPL", "interval": "4h"}),
            ("get_ohlcv", {"symbol": "NASDAQ:AAPL", "interval": "1D", "count": 300, "summary": False}),
            ("get_ohlcv", {"symbol": "NASDAQ:AAPL", "interval": "4h", "count": 300, "summary": False}),
        ])

    def test_failed_call_is_unknown(self):
        class Session:
            def call_tool(self, name, arguments):
                return {"status": "UNKNOWN", "response": None, "error": "request_failed"}

        result = TvremixTechnicalsClient(Session()).get("NASDAQ:AAPL")
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

