import unittest
from datetime import datetime, timezone

from earnings_monitor.exchange_calendar import completed_sessions_before
from earnings_monitor.staleness import assess_ohlcv_staleness


class CalendarStalenessIntegrationTests(unittest.TestCase):
    def test_real_calendar_feeds_staleness_assessment(self):
        # Candle closed at regular 16:00 ET close of Aug 13 (20:00 UTC).
        now = datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc)  # 09:00 EDT
        sessions = completed_sessions_before(now, lookback_days=10)
        result = assess_ohlcv_staleness(
            timeframe="1D",
            candle_close=datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc),
            now=now,
            completed_sessions=sessions,
        )
        self.assertEqual(result["state"], "FRESH")


if __name__ == "__main__":
    unittest.main()

      
