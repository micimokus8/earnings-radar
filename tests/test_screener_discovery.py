import unittest

from earnings_monitor.screener_discovery import parse_screener_rows


def _rows():
    return [
        {"symbol": "NYSE:BIGCAP", "name": "Big Cap Inc",
         "earnings_release_next_date": "2026-08-25",
         "earnings_release_time": 1, "market_cap_basic": 50_000_000_000},
        {"symbol": "NASDAQ:ZM", "name": "Zoom",
         "earnings_release_next_date": "2026-08-25",
         "earnings_release_time": 1, "market_cap_basic": 30_000_000_000},
        {"symbol": "NASDAQ:SMTC", "name": "Semtech",
         "earnings_release_next_date": "2026-08-25",
         "earnings_release_time": 1, "market_cap_basic": 3_000_000_000},
        {"symbol": "NYSE:LATER", "name": "Later Corp",
         "earnings_release_next_date": "2026-08-27",
         "market_cap_basic": 9_000_000_000},
        {"symbol": None, "earnings_release_next_date": "2026-08-25",
         "market_cap_basic": 1_000},
        {"symbol": "NASDAQ:DUP", "earnings_release_next_date": "2026-08-25",
         "market_cap_basic": 5_000_000_000},
        {"symbol": "NASDAQ:DUP", "earnings_release_next_date": "2026-08-25",
         "market_cap_basic": 5_000_000_000},
    ]


class ParseScreenerRowsTests(unittest.TestCase):
    def test_filters_target_date_preserves_server_order(self):
        result = parse_screener_rows(_rows(), target_date="2026-08-25")
        self.assertEqual(
            result,
            ["NYSE:BIGCAP", "NASDAQ:ZM", "NASDAQ:SMTC", "NASDAQ:DUP"],
        )

    def test_empty_rows(self):
        self.assertEqual(parse_screener_rows([], target_date="2026-08-25"), [])

    def test_no_match_other_dates_only(self):
        result = parse_screener_rows(_rows()[3:4], target_date="2026-08-25")
        self.assertEqual(result, [])

    def test_dual_class_shares_collapse_to_one(self):
        rows = [
            {"symbol": "NYSE:HEI", "name": "HEICO",
             "earnings_release_next_date": "2026-08-25", "market_cap_basic": 41_000_000_000},
            {"symbol": "NYSE:HEI.A", "name": "HEICO Class A",
             "earnings_release_next_date": "2026-08-25", "market_cap_basic": 41_000_000_000},
            {"symbol": "NASDAQ:SMTC", "name": "Semtech",
             "earnings_release_next_date": "2026-08-25", "market_cap_basic": 3_000_000_000},
        ]
        result = parse_screener_rows(rows, target_date="2026-08-25")
        self.assertEqual(result, ["NYSE:HEI", "NASDAQ:SMTC"])
        self.assertNotIn("NYSE:HEI.A", result)


if __name__ == "__main__":
    unittest.main()

      
