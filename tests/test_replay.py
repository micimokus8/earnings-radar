import unittest

from earnings_monitor.replay import run_fixture_report

FIXTURE = "tests/fixtures/replay_sample.json"


class ReplayTests(unittest.TestCase):
    def test_fixture_run_builds_complete_report(self):
        report = run_fixture_report(FIXTURE)
        self.assertEqual(report["report_id"], "2026-08-13:BEFORE_OPEN")
        self.assertEqual(report["quality"]["candidate_count"], 1)
        self.assertEqual(report["quality"]["incomplete_count"], 0)
        candidate = report["candidates"][0]
        self.assertEqual(candidate["status"], "PASS")
        self.assertEqual(candidate["score"]["label"], "SKIP")
        self.assertEqual(candidate["score"]["total_points"], 5)
        self.assertEqual(report["quality"]["missing_fields"], {})

    def test_fixture_runs_are_deterministic(self):
        first = run_fixture_report(FIXTURE)
        second = run_fixture_report(FIXTURE)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

      
