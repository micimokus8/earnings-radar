import unittest

from earnings_monitor.run_report import run_report


class _Pipeline:
    def run(self, symbols, *, as_of, date_from=None, date_to=None):
        return {
            "status": "PASS",
            "as_of": as_of,
            "candidates": [
                {
                    "symbol": symbols[0],
                    "status": "INCOMPLETE",
                    "missing": ["short_pct_outstanding"],
                    "score": {"total_points": 3, "label": None},
                }
            ],
        }


class RunReportTests(unittest.TestCase):
    def test_runs_pipeline_and_builds_report_for_stream(self):
        report = run_report(
            _Pipeline(),
            symbols=["NASDAQ:AAPL"],
            report_type="AFTER_CLOSE",
            report_date="2026-08-13",
            as_of="2026-08-13T16:30:00+00:00",
        )
        self.assertEqual(report["report_id"], "2026-08-13:AFTER_CLOSE")
        self.assertEqual(report["quality"]["candidate_count"], 1)
        self.assertEqual(report["quality"]["incomplete_count"], 1)
        self.assertEqual(report["candidates"][0]["symbol"], "NASDAQ:AAPL")


if __name__ == "__main__":
    unittest.main()

      
