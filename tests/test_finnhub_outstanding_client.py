import json
import tempfile
import unittest

from earnings_monitor.finnhub_outstanding_client import FinnhubOutstandingClient


_BODY = json.dumps({
    "symbol": "AAPL",
    "shareOutstanding": 14800.5,
}).encode("utf-8")


class FakeRequester:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def __call__(self, url, *, headers, timeout):
        self.calls.append({"url": url, "headers": headers})
        if self._error is not None:
            raise self._error
        return self._response


class FinnhubOutstandingClientTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        self._tmp.write("test-token-123")
        self._tmp.close()

    def test_reads_local_key_and_parses_shares_outstanding(self):
        requester = FakeRequester(response={"status": 200, "body": _BODY})
        client = FinnhubOutstandingClient(
            key_path=self._tmp.name, requester=requester
        )
        result = client.get("NASDAQ:AAPL")
        self.assertEqual(result["status"], "PASS")
        self.assertAlmostEqual(result["shares_outstanding_millions"], 14800.5)
        self.assertEqual(result["report_date"], None)
        headers = requester.calls[0]["headers"]
        self.assertEqual(headers["X-Finnhub-Token"], "test-token-123")
        self.assertNotIn("test-token-123", json.dumps(result))

    def test_missing_key_file_is_unknown(self):
        client = FinnhubOutstandingClient(
            key_path="/nonexistent/key.txt", requester=FakeRequester()
        )
        result = client.get("NASDAQ:AAPL")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_http_error_is_unknown(self):
        client = FinnhubOutstandingClient(
            key_path=self._tmp.name,
            requester=FakeRequester(response={"status": 403, "body": b""}),
        )
        result = client.get("NASDAQ:AAPL")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_transport_exception_is_unknown(self):
        client = FinnhubOutstandingClient(
            key_path=self._tmp.name,
            requester=FakeRequester(error=RuntimeError("timeout")),
        )
        result = client.get("NASDAQ:AAPL")
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

      
