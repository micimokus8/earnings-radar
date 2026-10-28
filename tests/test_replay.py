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
        # Das Fixture liefert keine 52W-/5d-Felder (Chart-Kategorie hat seit dem
        # Ausbau 5 Punkte). 3 Punkte sind fuer diesen Input korrekt; die
        # fehlenden Chart-Punkte muessen als unknown sichtbar bleiben und
        # duerfen die erreichbaren Punkte NICHT erhoehen.
        self.assertEqual(candidate["score"]["total_points"], 3)
        self.assertEqual(candidate["score"]["reachable_points"], 14)
        self.assertEqual(candidate["score"]["score_pct"], 21.4)
        chart = candidate["score"]["categories"]["chart_confirmation"]
        self.assertEqual(chart["state"], "PARTIAL")
        self.assertIn("distance_to_52w_pct", chart["unknown"])
        self.assertEqual(report["quality"]["missing_fields"], {})

    def test_fixture_runs_are_deterministic(self):
        first = run_fixture_report(FIXTURE)
        second = run_fixture_report(FIXTURE)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

      
