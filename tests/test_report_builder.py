import unittest

from earnings_monitor.report_builder import build_report, merge_reports


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

    def test_truncated_flag_propagates_to_quality(self):
        candidates = [{
            "symbol": "NASDAQ:AAPL", "status": "PASS",
            "score": {"total_points": 10, "label": "STRONG_SETUP"}, "missing": [],
        }]
        report = build_report(
            report_type="BEFORE_OPEN", report_date="2026-08-13",
            as_of="2026-08-13T09:30:00+00:00",
            candidates=candidates, truncated=True,
        )
        self.assertTrue(report["quality"]["truncated"])

    def test_merge_reports_combines_candidates_without_drops_or_dups(self):
        a = build_report(
            report_type="BEFORE_OPEN", report_date="2026-08-13",
            as_of="2026-08-13T09:30:00+00:00",
            candidates=[{
                "symbol": "NASDAQ:AAPL", "status": "PASS",
                "score": {"total_points": 10, "label": "STRONG_SETUP"}, "missing": [],
            }],
        )
        b = build_report(
            report_type="BEFORE_OPEN", report_date="2026-08-13",
            as_of="2026-08-13T09:31:00+00:00",
            candidates=[
                {"symbol": "NASDAQ:MSFT", "status": "INCOMPLETE",
                 "score": {"total_points": 3, "label": None},
                 "missing": ["short_pct_outstanding"]},
                {"symbol": "NASDAQ:AAPL", "status": "PASS",  # duplicate -> kept once
                 "score": {"total_points": 5, "label": None}, "missing": []},
            ],
        )
        merged = merge_reports([a, b])
        symbols = {c["symbol"] for c in merged["candidates"]}
        self.assertEqual(symbols, {"NASDAQ:AAPL", "NASDAQ:MSFT"})
        self.assertEqual(merged["quality"]["candidate_count"], 2)
        self.assertEqual(merged["quality"]["incomplete_count"], 1)

    def test_merge_preserves_lost_symbols_flagged(self):
        a = build_report(
            report_type="AFTER_CLOSE", report_date="2026-08-26",
            as_of="2026-08-26T16:30:00+00:00",
            candidates=[{
                "symbol": "NASDAQ:NVDA", "status": "PASS",
                "score": {"total_points": 5, "label": "SKIP"}, "missing": [],
            }],
            lost_symbols=["NYSE:CRM", "NASDAQ:CRWD"],
        )
        merged = merge_reports([a])
        self.assertIn("NYSE:CRM", merged["quality"]["lost_symbols"])
        self.assertIn("NASDAQ:CRWD", merged["quality"]["lost_symbols"])


if __name__ == "__main__":
    unittest.main()

      
