import unittest

from earnings_monitor.report_builder import build_report


class ReportBuilderTests(unittest.TestCase):
    def test_builds_deterministic_stream_report_with_quality_summary(self):
        candidates = [
            {
                "symbol": "NASDAQ:MSFT",
                "status": "INCOMPLETE",
                "score": {"total_points": 4, "label": None},
                "missing": ["short_pct_outstanding", "days_to_cover"],
            },
            {
                "symbol": "NASDAQ:AAPL",
                "status": "PASS",
                "score": {"total_points": 10, "label": "STRONG_SETUP"},
                "missing": [],
            },
        ]

        report = build_report(
            report_type="BEFORE_OPEN",
            report_date="2026-08-13",
            as_of="2026-08-13T09:30:00+00:00",
            candidates=candidates,
        )

        self.assertEqual(report["report_id"], "2026-08-13:BEFORE_OPEN")
        self.assertEqual(report["report_type"], "BEFORE_OPEN")
        self.assertEqual([row["symbol"] for row in report["candidates"]], [
            "NASDAQ:AAPL", "NASDAQ:MSFT"
        ])
        self.assertEqual(report["quality"]["candidate_count"], 2)
        self.assertEqual(report["quality"]["incomplete_count"], 1)
        self.assertEqual(report["quality"]["missing_fields"], {
            "days_to_cover": 1,
            "short_pct_outstanding": 1,
        })


if __name__ == "__main__":
    unittest.main()

      
