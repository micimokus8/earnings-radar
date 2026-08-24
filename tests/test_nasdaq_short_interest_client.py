import json
import unittest

from earnings_monitor.nasdaq_short_interest_client import NasdaqShortInterestClient


_BODY = json.dumps({
    "data": {
        "symbol": "aapl",
        "shortInterestTable": {
            "rows": [
                {"settlementDate": "07/31/2026", "interest": "141,606,163",
                 "avgDailyShareVolume": "58,400,983", "daysToCover": 2.424722},
            ]
        },
    }
}).encode("utf-8")


class FakeRequester:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def __call__(self, url, *, headers, timeout):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        if self._error is not None:
            raise self._error
        return self._response


class NasdaqShortInterestClientTests(unittest.TestCase):
    def test_successful_fetch_returns_normalized_values(self):
        requester = FakeRequester(response={"status": 200, "body": _BODY})
        client = NasdaqShortInterestClient(requester=requester)

        result = client.get("NASDAQ:AAPL", as_of="2026-08-13T09:30:00+00:00")

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["report_date"], "2026-07-31")
        self.assertEqual(result["shares_short"], 141_606_163)
        url = requester.calls[0]["url"]
        self.assertIn("/api/quote/AAPL/short-interest", url)
        self.assertIn("assetclass=stocks", url)
        self.assertTrue(requester.calls[0]["headers"].get("User-Agent"))

    def test_http_error_returns_unknown(self):
        client = NasdaqShortInterestClient(
            requester=FakeRequester(response={"status": 403, "body": b""})
        )
        result = client.get("NASDAQ:AAPL", as_of="2026-08-13")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_transport_exception_returns_unknown(self):
        client = NasdaqShortInterestClient(
            requester=FakeRequester(error=RuntimeError("network down"))
        )
        result = client.get("NASDAQ:AAPL", as_of="2026-08-13")
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

      
