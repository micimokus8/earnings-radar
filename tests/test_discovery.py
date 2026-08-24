import unittest

from earnings_monitor.discovery import discover_earnings_symbols


class DiscoveryTests(unittest.TestCase):
    def test_selects_symbols_matching_target_date(self):
        events = [
            {"symbol": "NASDAQ:AAPL", "earnings_date": "2026-08-24"},
            {"symbol": "NASDAQ:OLD", "earnings_date": "2026-08-21"},
            {"symbol": "NYSE:BAC", "earnings_date": "2026-08-24"},
        ]
        result = discover_earnings_symbols(events, target_date="2026-08-24")
        self.assertEqual(result, ["NASDAQ:AAPL", "NYSE:BAC"])

    def test_deduplicates_and_skips_missing_symbol_or_date(self):
        events = [
            {"symbol": "NASDAQ:AAPL", "earnings_date": "2026-08-24"},
            {"symbol": "NASDAQ:AAPL", "earnings_date": "2026-08-24"},
            {"symbol": None, "earnings_date": "2026-08-24"},
            {"symbol": "NYSE:X", "earnings_date": None},
        ]
        result = discover_earnings_symbols(events, target_date="2026-08-24")
        self.assertEqual(result, ["NASDAQ:AAPL"])

    def test_no_matches_returns_empty(self):
        result = discover_earnings_symbols(
            [{"symbol": "NYSE:X", "earnings_date": "2026-01-02"}],
            target_date="2026-08-24",
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()

      
