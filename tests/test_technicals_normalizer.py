import unittest

from earnings_monitor.technicals_normalizer import normalize_technicals_for_score


class TechnicalsNormalizerTests(unittest.TestCase):
    def test_maps_client_output_to_score_fields(self):
        bars_1d = [
            {"t": i, "o": 100 + i, "h": 101 + i, "l": 99 + i, "c": 100 + i, "v": 1000}
            for i in range(60)
        ]
        bars_4h = [
            {"t": i, "o": 200 + i, "h": 201 + i, "l": 199 + i, "c": 200 + i, "v": 1000}
            for i in range(60)
        ]
        result = normalize_technicals_for_score({
            "status": "PASS",
            "technicals": {
                "1D": {"price": 159.0, "rsi": 39.0},
                "4h": {"price": 259.0, "rsi": 38.0},
            },
            "ohlcv": {
                "1D": {"status": "PASS", "bars": bars_1d},
                "4h": {"status": "PASS", "bars": bars_4h},
            },
        })
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["values"]["price_1d"], 159.0)
        self.assertEqual(result["values"]["price_4h"], 259.0)
        self.assertIsNotNone(result["values"]["ema20_1d"])
        self.assertIsNotNone(result["values"]["ema50_1d"])
        self.assertIsNotNone(result["values"]["ema20_4h"])
        self.assertEqual(result["values"]["rsi_1d"], 39.0)
        self.assertIsNotNone(result["values"]["adx_1d"])

    def test_unknown_client_keeps_technical_values_missing(self):
        result = normalize_technicals_for_score({"status": "UNKNOWN"})
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["values"]["price_1d"])
        self.assertIsNone(result["values"]["ema20_1d"])
        self.assertIn("client_status", result["unknown"])


if __name__ == "__main__":
    unittest.main()

