import unittest

from earnings_monitor.short_interest_provider import ShortInterestProvider


class _FakeNasdaq:
    def get(self, symbol, *, as_of):
        return {"status": "PASS", "report_date": "2026-07-31",
                "shares_short": 141_606_163, "days_to_cover": 2.42}


class _FakeOutstanding:
    def __init__(self, value):
        self._value = value

    def get(self, symbol):
        if self._value is None:
            return {"status": "UNKNOWN", "shares_outstanding_millions": None,
                    "report_date": None}
        return {"status": "PASS", "shares_outstanding_millions": self._value,
                "report_date": None}


class ShortInterestProviderTests(unittest.TestCase):
    def test_combines_both_clients_into_score_values(self):
        provider = ShortInterestProvider(
            nasdaq=_FakeNasdaq(), outstanding=_FakeOutstanding(14_800.0)
        )
        result = provider.get("NASDAQ:AAPL", as_of="2026-08-13T09:30:00+00:00")
        self.assertEqual(result["status"], "PASS")
        self.assertAlmostEqual(result["short_pct_outstanding"], 0.9568, places=3)
        self.assertEqual(result["days_to_cover"], 2.42)

    def test_missing_outstanding_degrades_to_partial(self):
        provider = ShortInterestProvider(
            nasdaq=_FakeNasdaq(), outstanding=_FakeOutstanding(None)
        )
        result = provider.get("NASDAQ:AAPL", as_of="2026-08-13")
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIsNone(result["short_pct_outstanding"])
        self.assertEqual(result["days_to_cover"], 2.42)

    def test_non_nasdaq_symbol_is_exchange_na_not_error(self):
        provider = ShortInterestProvider(
            nasdaq=_FakeNasdaq(), outstanding=_FakeOutstanding(14_800.0)
        )
        result = provider.get("NYSE:HEI", as_of="2026-08-13T16:00:00+00:00")
        self.assertEqual(result["status"], "N/A")
        self.assertTrue(result["exchange_unsupported"])
        self.assertIsNone(result["short_pct_outstanding"])
        self.assertIsNone(result["days_to_cover"])


if __name__ == "__main__":
    unittest.main()

      
