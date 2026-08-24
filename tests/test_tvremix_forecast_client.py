import unittest

from earnings_monitor.tvremix_forecast_client import TvremixForecastClient


class TvremixForecastClientTests(unittest.TestCase):
    def test_calls_verified_tool_and_normalizes_response(self):
        calls = []

        class Transport:
            def call(self, url, payload):
                calls.append((url, payload))
                return {
                    "status": "PASS",
                    "response": {
                        "result": {"content": [{"type": "text", "text":
                            '{"success":true,"data":{"analyst_rating":{"recommendation":"buy"},'
                            '"price_targets":{"average":150,"upside_pct":25},'
                            '"estimates":{"eps_next_quarter":1.4}}}'
                        }]}
                    },
                }

        client = TvremixForecastClient(Transport(), "https://example.test/mcp")
        result = client.get("NASDAQ:AAPL", price=120)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["forecast"]["analyst_rating"], "buy")
        self.assertEqual(calls[0][1]["method"], "tools/call")
        self.assertEqual(calls[0][1]["params"]["name"], "get_forecasts")
        self.assertEqual(calls[0][1]["params"]["arguments"], {"symbol": "NASDAQ:AAPL"})

    def test_session_transport_calls_verified_tool(self):
        calls = []

        class Session:
            def call_tool(self, name, arguments):
                calls.append((name, arguments))
                return {
                    "status": "PASS",
                    "response": {
                        "result": {"content": [{"type": "text", "text":
                            '{"success":true,"data":{"analyst_rating":{"recommendation":"buy"},'
                            '"price_targets":{"average":150,"upside_pct":25},'
                            '"estimates":{"eps_next_quarter":1.4}}}'
                        }]}
                    },
                }

        result = TvremixForecastClient(Session(), "https://example.test/mcp").get(
            "NASDAQ:AAPL", price=120
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(calls, [("get_forecasts", {"symbol": "NASDAQ:AAPL"})])

    def test_transport_failure_is_unknown(self):
        class Transport:
            def call(self, url, payload):
                return {"status": "UNKNOWN", "response": None, "error": "request_failed"}

        result = TvremixForecastClient(Transport(), "https://example.test/mcp").get("AAPL", price=120)
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

