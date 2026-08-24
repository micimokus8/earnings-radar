import unittest
from datetime import datetime, timezone

from earnings_monitor.staleness import assess_ohlcv_staleness


UTC = timezone.utc


class StalenessTests(unittest.TestCase):
    def test_daily_candle_is_fresh_on_next_calendar_day(self):
        result = assess_ohlcv_staleness(
            timeframe="1D",
            candle_close=datetime(2026, 8, 11, 20, 0, tzinfo=UTC),
            now=datetime(2026, 8, 12, 13, 0, tzinfo=UTC),
            completed_sessions=["2026-08-11", "2026-08-12"],
        )
        self.assertEqual(result["state"], "FRESH")

    def test_weekend_does_not_make_last_friday_daily_data_stale(self):
        result = assess_ohlcv_staleness(
            timeframe="1D",
            candle_close=datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
            now=datetime(2026, 8, 17, 13, 0, tzinfo=UTC),
            completed_sessions=["2026-08-14", "2026-08-17"],
        )
        self.assertEqual(result["state"], "FRESH")

    def test_missing_session_calendar_is_unknown(self):
        result = assess_ohlcv_staleness(
            timeframe="1D",
            candle_close=datetime(2026, 8, 11, 20, 0, tzinfo=UTC),
            now=datetime(2026, 8, 12, 13, 0, tzinfo=UTC),
            completed_sessions=None,
        )
        self.assertEqual(result["state"], "UNKNOWN")

    def test_unclosed_intraday_candle_is_not_accepted(self):
        result = assess_ohlcv_staleness(
            timeframe="4H",
            candle_close=datetime(2026, 8, 12, 16, 0, tzinfo=UTC),
            now=datetime(2026, 8, 12, 15, 30, tzinfo=UTC),
            completed_sessions=["2026-08-12"],
        )
        self.assertEqual(result["state"], "STALE")


if __name__ == "__main__":
    unittest.main()


class NasdaqTimingTests(unittest.TestCase):
    pass
