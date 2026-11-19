import unittest
from datetime import datetime, timezone

from earnings_monitor.bars import drop_unfinished_daily
from earnings_monitor.earnings_history import summarize_earnings_history
from earnings_monitor.outcomes import session_returns
from earnings_monitor.freshness import drift_reason, format_priced_at, recompute_with_live_price
from earnings_monitor.schedule import plan_scan, stage_for


class ScheduleTests(unittest.TestCase):
    def test_after_close_scan_is_open_at_19_utc_in_winter_and_summer(self):
        winter = datetime(2026, 1, 15, 19, 0, tzinfo=timezone.utc)  # 14:00 EST
        summer = datetime(2026, 7, 15, 19, 0, tzinfo=timezone.utc)  # 15:00 EDT
        for moment in (winter, summer):
            plan = plan_scan("AFTER_CLOSE", moment)
            self.assertTrue(plan.entry_open, moment.isoformat())
            self.assertIn("16:00", plan.headline)

    def test_after_close_scan_stops_once_the_cash_session_is_over(self):
        late = datetime(2026, 1, 15, 22, 0, tzinfo=timezone.utc)  # 17:00 EST
        plan = plan_scan("AFTER_CLOSE", late)
        self.assertFalse(plan.entry_open)
        self.assertIn("geschlossen", plan.blocked_reason)

    def test_before_open_evening_targets_the_next_session(self):
        # Thursday 23:00 UTC = 18:00 EST, next session is Friday.
        evening = datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc)
        plan = plan_scan("BEFORE_OPEN", evening)
        self.assertEqual(plan.target_date, "2026-01-16")
        self.assertIn("Vortags", plan.horizon)

    def test_final_window_is_30_to_45_minutes_before_the_close_in_both_seasons(self):
        winter = datetime(2026, 1, 15, 20, 15, tzinfo=timezone.utc)  # 15:15 EST
        summer = datetime(2026, 7, 15, 19, 15, tzinfo=timezone.utc)  # 15:15 EDT
        self.assertEqual(stage_for("AFTER_CLOSE", winter), "final")
        self.assertEqual(stage_for("BEFORE_OPEN", summer), "final")

    def test_midday_is_preselect_in_both_seasons(self):
        winter = datetime(2026, 1, 15, 17, 0, tzinfo=timezone.utc)  # 12:00 EST
        summer = datetime(2026, 7, 15, 17, 0, tzinfo=timezone.utc)  # 13:00 EDT
        self.assertEqual(stage_for("AFTER_CLOSE", winter), "preselect")
        self.assertEqual(stage_for("BEFORE_OPEN", summer), "preselect")

    def test_before_open_early_morning_targets_the_same_day(self):
        early = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)  # 07:00 EST
        plan = plan_scan("BEFORE_OPEN", early)
        self.assertEqual(plan.target_date, "2026-01-15")


class FreshnessTests(unittest.TestCase):
    def test_large_moves_since_preselect_are_blocked(self):
        self.assertEqual(drift_reason(6.0, 5, 5), "SCHON_GELAUFEN")
        self.assertEqual(drift_reason(-6.0, 5, 5), "SCHARFER_RUECKGANG")
        self.assertIsNone(drift_reason(1.2, 5, 5))

    def test_live_price_updates_rsi_inputs_and_clocks_are_labelled(self):
        bars = [{"high": 10 + i, "low": 9 + i, "close": 9.5 + i} for i in range(40)]
        values = recompute_with_live_price({"price_1d": 48}, bars, 60)
        self.assertEqual(values["price"], 60)
        self.assertGreater(values["high_52w"], 48)
        text = format_priced_at(datetime(2026, 1, 15, 20, 15, tzinfo=timezone.utc))
        self.assertIn("New York", text)
        self.assertIn("Berlin", text)
        self.assertIn("15:15", text)

    def test_entry_price_is_the_final_check_not_the_official_close(self):
        bars = [
            {"date": "2026-01-14", "open": 100, "close": 100},
            {"date": "2026-01-15", "open": 101, "close": 110},
            {"date": "2026-01-16", "open": 121, "close": 115},
        ]
        checked = session_returns(
            report_type="AFTER_CLOSE", report_date="2026-01-15",
            bars=bars, entry_price=112,
        )
        self.assertAlmostEqual(checked["ret_session_close"], (115 / 112 - 1) * 100, places=2)
        self.assertAlmostEqual(checked["ret_official_close"], (115 / 110 - 1) * 100, places=2)


class BarTests(unittest.TestCase):
    def test_unfinished_daily_bar_is_dropped_before_the_close(self):
        now = datetime(2026, 1, 15, 19, 0, tzinfo=timezone.utc)  # 14:00 EST
        bars = [
            {"datetime": "2026-01-14", "c": 10, "h": 11, "l": 9},
            {"datetime": "2026-01-15", "c": 12, "h": 13, "l": 11},
        ]
        kept = drop_unfinished_daily(bars, now)
        self.assertEqual([bar["datetime"] for bar in kept], ["2026-01-14"])

    def test_completed_bar_stays_after_the_close(self):
        now = datetime(2026, 1, 15, 22, 0, tzinfo=timezone.utc)  # 17:00 EST
        bars = [{"datetime": "2026-01-15", "c": 12, "h": 13, "l": 11}]
        self.assertEqual(len(drop_unfinished_daily(bars, now)), 1)


class HistoryAndOutcomeTests(unittest.TestCase):
    def test_history_uses_only_prior_prints_and_known_sessions(self):
        events = [
            {"date": "2025-01-15", "hour": "amc", "eps_actual": 1.2, "eps_estimate": 1.0},
            {"date": "2025-04-15", "hour": "bmo", "eps_actual": 0.8, "eps_estimate": 1.0},
            {"date": "2025-07-15", "hour": "amc", "eps_actual": 1.4, "eps_estimate": 1.1},
            {"date": "2025-10-15", "hour": "bmo", "eps_actual": 1.3, "eps_estimate": 1.0},
            {"date": "2026-01-15", "hour": "amc", "eps_actual": 9.0, "eps_estimate": 1.0},
        ]
        bars = []
        price = 100.0
        for day, close in (
            ("2025-01-15", 100), ("2025-01-16", 110),
            ("2025-04-14", 100), ("2025-04-15", 90),
            ("2025-07-15", 100), ("2025-07-16", 105),
            ("2025-10-14", 100), ("2025-10-15", 108),
        ):
            bars.append({"date": day, "close": close, "open": close})
        summary = summarize_earnings_history(events, bars, as_of="2026-01-14")
        self.assertEqual(summary["beat_n"], 4)
        self.assertEqual(summary["beat_rate"], 0.75)
        self.assertEqual(summary["hist_n"], 4)
        # The upcoming 2026 print is excluded.
        self.assertNotEqual(summary["hist_reaction_pct"], 800)

    def test_after_close_return_is_next_session_and_before_open_is_the_same_day(self):
        bars = [
            {"date": "2026-01-14", "open": 100, "close": 100},
            {"date": "2026-01-15", "open": 101, "close": 110},
            {"date": "2026-01-16", "open": 121, "close": 115},
        ]
        after = session_returns(report_type="AFTER_CLOSE", report_date="2026-01-15", bars=bars)
        self.assertEqual(after["verdict"], "FLAT")
        self.assertAlmostEqual(after["ret_session_open"], 10.0)
        self.assertAlmostEqual(after["ret_session_close"], 4.545, places=2)
        before = session_returns(report_type="BEFORE_OPEN", report_date="2026-01-15", bars=bars)
        self.assertEqual(before["verdict"], "PUMP")
        self.assertAlmostEqual(before["ret_session_open"], 1.0)
        self.assertAlmostEqual(before["ret_session_close"], 10.0)


if __name__ == "__main__":
    unittest.main()
