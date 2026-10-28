import json
import unittest
from datetime import date

from earnings_monitor.earningswhispers import EarningsWhispersClient


class _Resp:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class _Opener:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def open(self, request, timeout=None):
        self.urls.append(request.full_url)
        return _Resp(self.payload)


def _client(payload):
    client = EarningsWhispersClient(timeout=5)
    client._session_initialized = True          # Kalender-Seite ueberspringen
    opener = _Opener(payload)
    client._opener = opener
    return client, opener


class NewCalDataEndpointTests(unittest.TestCase):
    """EW hat /api/quickcaldata/<date>/<session> abgeschaltet (404 am 28.10.)."""

    def test_uses_caldata_endpoint(self):
        client, opener = _client([{"ticker": "MSFT", "releaseTime": 3}])
        client.get_symbols(target_date=date(2026, 10, 28), report_type="AFTER_CLOSE")
        self.assertEqual(opener.urls[-1],
                         "https://www.earningswhispers.com/api/caldata/20261028")

    def test_after_close_filters_release_time_three(self):
        payload = [
            {"ticker": "MSFT", "releaseTime": 3},
            {"ticker": "CAT", "releaseTime": 1},
            {"ticker": "GOOGL", "releaseTime": 3},
        ]
        client, _ = _client(payload)
        symbols = client.get_symbols(target_date=date(2026, 10, 28), report_type="AFTER_CLOSE")
        self.assertEqual(symbols, ["MSFT", "GOOGL"])

    def test_before_open_filters_release_time_one(self):
        payload = [
            {"ticker": "MSFT", "releaseTime": 3},
            {"ticker": "CAT", "releaseTime": 1},
        ]
        client, _ = _client(payload)
        symbols = client.get_symbols(target_date=date(2026, 10, 29), report_type="BEFORE_OPEN")
        self.assertEqual(symbols, ["CAT"])

    def test_duplicates_are_removed(self):
        payload = [
            {"ticker": "GOOGL", "releaseTime": 3},
            {"ticker": "GOOGL", "releaseTime": 3},
            {"ticker": "GOOG", "releaseTime": 3},
        ]
        client, _ = _client(payload)
        symbols = client.get_symbols(target_date=date(2026, 10, 28), report_type="AFTER_CLOSE")
        self.assertEqual(symbols, ["GOOGL", "GOOG"])

    def test_payload_without_release_time_is_not_filtered(self):
        payload = [{"ticker": "AAA"}, {"ticker": "BBB"}]
        client, _ = _client(payload)
        symbols = client.get_symbols(target_date=date(2026, 10, 28), report_type="AFTER_CLOSE")
        self.assertEqual(symbols, ["AAA", "BBB"])

    def test_empty_payload_returns_none(self):
        client, _ = _client([])
        self.assertIsNone(
            client.get_symbols(target_date=date(2026, 10, 28), report_type="AFTER_CLOSE")
        )


if __name__ == "__main__":
    unittest.main()
