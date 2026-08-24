import tempfile
import unittest
from pathlib import Path

from earnings_monitor.forecast_target_pipeline import evaluate_target_change


class ForecastTargetPipelineTests(unittest.TestCase):
    def test_previous_target_cut_is_detected_and_current_target_is_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            store_path = Path(directory) / "targets.json"
            first = evaluate_target_change(
                store_path=store_path,
                symbol="ABC",
                forecast={"price_targets": {"average": 100.0}},
                as_of="2026-08-01T10:00:00+00:00",
            )
            self.assertEqual(first["status"], "UNKNOWN")
            self.assertIsNone(first["cut"])

            second = evaluate_target_change(
                store_path=store_path,
                symbol="ABC",
                forecast={"price_targets": {"average": 97.0}},
                as_of="2026-08-12T10:00:00+00:00",
            )
            self.assertEqual(second["status"], "PASS")
            self.assertTrue(second["cut"])
            self.assertEqual(second["previous_average"], 100.0)
            self.assertEqual(second["current_average"], 97.0)


if __name__ == "__main__":
    unittest.main()
