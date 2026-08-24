import unittest
from datetime import date, datetime, timezone

from earnings_monitor.exchange_calendar import (
    completed_sessions_before,
    early_close_dates,
    nyse_holidays,
    trading_sessions,
)


class NyseHolidaysTests(unittest.TestCase):
    def test_holidays_2026_with_known_reference_dates(self):
        holidays = nyse_holidays(2026)
        expected = {
            date(2026, 1, 1),    # New Year (Thu)
            date(2026, 1, 19),   # MLK (3rd Mon)
            date(2026, 2, 16),   # Presidents (3rd Mon)
            date(2026, 4, 3),    # Good Friday (Easter Apr 5)
            date(2026, 5, 25),   # Memorial (last Mon)
            date(2026, 6, 19),   # Juneteenth (Fri)
            date(2026, 7, 3),    # July 4 observed (falls Sat -> Fri)
            date(2026, 9, 7),    # Labor (1st Mon)
            date(2026, 11, 26),  # Thanksgiving (4th Thu)
            date(2026, 12, 25),  # Christmas (Fri)
        }
        self.assertEqual(holidays, expected)

    def test_sunday_holiday_observed_on_monday(self):
        # July 4, 2027 is a Sunday -> observed Monday July 5
        self.assertIn(date(2027, 7, 5), nyse_holidays(2027))


class EarlyCloseTests(unittest.TestCase):
    def test_early_closes_2026(self):
        self.assertEqual(
            early_close_dates(2026),
            {date(2026, 11, 27), date(2026, 12, 24)},
        )


class TradingSessionsTests(unittest.TestCase):
    def test_range_skips_holiday_and_weekend(self):
        sessions = trading_sessions(date(2026, 7, 2), date(2026, 7, 6))
        self.assertEqual(sessions, [date(2026, 7, 2), date(2026, 7, 6)])


class CompletedSessionsTests(unittest.TestCase):
    def test_regular_close_completed_after_16_et(self):
        now = datetime(2026, 8, 13, 20, 30, tzinfo=timezone.utc)  # 16:30 EDT
        sessions = completed_sessions_before(now, lookback_days=7)
        self.assertIn(date(2026, 8, 13), sessions)
        self.assertNotIn(date(2026, 8, 14), sessions)

    def test_early_close_completes_at_13_et(self):
        before = datetime(2026, 11, 27, 17, 59, tzinfo=timezone.utc)  # 12:59 EST
        after = datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)    # 13:00 EST
        self.assertNotIn(
            date(2026, 11, 27),
            completed_sessions_before(before, lookback_days=7),
        )
        self.assertIn(
            date(2026, 11, 27),
            completed_sessions_before(after, lookback_days=7),
        )

    def test_no_future_or_weekend_sessions(self):
        now = datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc)  # 10:00 EDT
        sessions = completed_sessions_before(now, lookback_days=7)
        self.assertNotIn(date(2026, 8, 13), sessions)  # still open
        self.assertNotIn(date(2026, 8, 8), sessions)   # Saturday


if __name__ == "__main__":
    unittest.main()

      
