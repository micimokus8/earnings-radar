import unittest

from earnings_monitor.forecasts import normalize_forecast


class ForecastTests(unittest.TestCase):
    def test_normalizes_forecast_fields(self):
        raw = {
            "analyst_rating": "buy",
            "price_targets": {"average": 150, "upside_pct": 25},
            "estimates": {"eps_next_quarter": 1.4},
        }
        result = normalize_forecast(raw, price=120)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["analyst_rating"], "buy")
        self.assertEqual(result["target_average"], 150)
        self.assertEqual(result["target_upside_pct"], 25)
        self.assertEqual(result["eps_estimate"], 1.4)

    def test_missing_forecast_is_unknown(self):
        result = normalize_forecast(None, price=120)
        self.assertEqual(result["status"], "UNKNOWN")

    def test_missing_eps_is_partial(self):
        raw = {"price_targets": {"average": 150, "upside_pct": 25}}
        result = normalize_forecast(raw, price=120)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIn("eps_estimate", result["missing"])


if __name__ == "__main__":
    unittest.main()
