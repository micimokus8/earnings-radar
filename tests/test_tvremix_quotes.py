import unittest

from earnings_monitor.tvremix_quotes import parse_tvremix_quotes_response


class TvremixQuotesTests(unittest.TestCase):
    def test_parses_mcp_batch_quote_map(self):
        response = {
            "result": {"content": [{"type": "text", "text":
                '{"success":true,"data":{"NASDAQ:AAPL":{"price":200.5,'
                '"market_cap":3000000000000,"volume":123456,"change_percent":1.2}}}'
            }]}
        }
        result = parse_tvremix_quotes_response(response)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["quotes"]["NASDAQ:AAPL"]["price"], 200.5)
        self.assertEqual(result["quotes"]["NASDAQ:AAPL"]["market_cap"], 3000000000000)

    def test_invalid_quote_data_is_unknown(self):
        result = parse_tvremix_quotes_response({"data": []})
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

