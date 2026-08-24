import json
import unittest

from earnings_monitor.tvremix_technicals import (
    parse_tvremix_ohlcv_response,
    parse_tvremix_technicals_response,
)


def mcp_payload(payload):
    return {"result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}


class TvremixTechnicalsTests(unittest.TestCase):
    def test_parses_verified_technicals_shape(self):
        response = mcp_payload({
            "success": True,
            "data": {
                "price": 200.5,
                "change": 1.2,
                "volume": 123,
                "oscillators": {"rsi": 42.5},
                "summary": {"recommendation": "BUY", "value": 0.1},
            },
        })
        result = parse_tvremix_technicals_response(response)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["technicals"]["price"], 200.5)
        self.assertEqual(result["technicals"]["rsi"], 42.5)

    def test_parses_verified_ohlcv_shape(self):
        response = mcp_payload({
            "success": True,
            "symbol": "NASDAQ:AAPL",
            "interval": "1D",
            "count": 2,
            "bars": [
                {"t": 1, "o": 10, "h": 12, "l": 9, "c": 11, "v": 100},
                {"t": 2, "o": 11, "h": 13, "l": 10, "c": 12, "v": 110},
            ],
            "summary": {},
        })
        result = parse_tvremix_ohlcv_response(response)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["bars"]), 2)
        self.assertEqual(result["bars"][0]["c"], 11)

    def test_invalid_technicals_or_bars_are_unknown(self):
        self.assertEqual(parse_tvremix_technicals_response({})["status"], "UNKNOWN")
        self.assertEqual(parse_tvremix_ohlcv_response(mcp_payload({"bars": [{"c": 1}]}))["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()


__all__ = ["TvremixTechnicalsTests"]

