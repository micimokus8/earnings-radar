import unittest

from earnings_monitor.report_state import ReportState


class ReportSeparationTests(unittest.TestCase):
    def test_morning_and_afternoon_are_separate_report_streams(self):
        state = ReportState()
        morning = state.start("BEFORE_OPEN", report_date="2026-08-12")
        afternoon = state.start("AFTER_CLOSE", report_date="2026-08-12")

        self.assertNotEqual(morning["report_id"], afternoon["report_id"])
        self.assertEqual(state.active_report("BEFORE_OPEN")["report_id"], morning["report_id"])
        self.assertEqual(state.active_report("AFTER_CLOSE")["report_id"], afternoon["report_id"])

    def test_cleanup_only_removes_requested_report_type(self):
        state = ReportState()
        morning = state.start("BEFORE_OPEN", report_date="2026-08-12")
        afternoon = state.start("AFTER_CLOSE", report_date="2026-08-12")
        state.cleanup("BEFORE_OPEN")

        self.assertIsNone(state.get(morning["report_id"]))
        self.assertIsNotNone(state.get(afternoon["report_id"]))


if __name__ == "__main__":
    unittest.main()
