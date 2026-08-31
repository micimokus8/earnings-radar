import unittest

from earnings_monitor.tvremix_forecasts import parse_tvremix_forecast_response


class TvremixForecastTests(unittest.TestCase):
    def test_parses_verified_mcp_content_shape(self):
        response = {
            "result": {
                "content": [{
                    "type": "text",
                    "text": '{"success":true,"data":{"analyst_rating":{"recommendation":"buy"},"price_targets":{"average":150,"upside_pct":25},"estimates":{"eps_next_quarter":1.4}}}',
                }]
            }
        }
        result = parse_tvremix_forecast_response(response)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["forecast"]["analyst_rating"], "buy")
        self.assertEqual(result["forecast"]["target_average"], 150)

    def test_parses_direct_data_forecast_response(self):
        response = {
            "data": {
                "analyst_rating": "buy",
                "price_targets": {"average": 150, "upside_pct": 25},
                "estimates": {"eps_next_quarter": 1.4},
            }
        }
        result = parse_tvremix_forecast_response(response)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["forecast"]["eps_estimate"], 1.4)

    def test_parses_results_forecast_response(self):
        response = {
            "results": [{
                "analyst_rating": "hold",
                "price_targets": {"average": 100, "upside_pct": 5},
                "estimates": {"eps_next_quarter": 0.8},
            }]
        }
        result = parse_tvremix_forecast_response(response)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["forecast"]["analyst_rating"], "hold")

    def test_provider_no_data_is_explicitly_unknown(self):
        result = parse_tvremix_forecast_response({
            "success": False,
            "error": "No analyst forecast data for NASDAQ:CANG",
        })
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["error"], "no_forecast_data")
        self.assertIn("No analyst forecast data", result["provider_error"])
        self.assertIsNone(result["forecast"])

    def test_malformed_response_is_unknown(self):
        result = parse_tvremix_forecast_response({"data": "bad"})
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

