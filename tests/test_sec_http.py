import gzip
import json
import unittest

from earnings_monitor.sec_http import SecHttpClient, SecHttpError


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, *, headers, timeout):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class SecHttpTests(unittest.TestCase):
    def test_user_agent_and_timeout_are_sent(self):
        transport = FakeTransport([{"status": 200, "headers": {}, "body": b"{}"}])
        client = SecHttpClient(
            user_agent="EarningsMonitor contact@example.invalid",
            transport=transport,
            timeout=7,
            retries=0,
        )
        self.assertEqual(client.get_json("https://data.sec.gov/test"), {})
        self.assertEqual(transport.calls[0]["headers"]["User-Agent"], "EarningsMonitor contact@example.invalid")
        self.assertEqual(transport.calls[0]["timeout"], 7)

    def test_gzip_response_is_decoded(self):
        body = gzip.compress(json.dumps({"ok": True}).encode())
        transport = FakeTransport([{"status": 200, "headers": {"Content-Encoding": "gzip"}, "body": body}])
        client = SecHttpClient(user_agent="test", transport=transport, retries=0)
        self.assertEqual(client.get_json("https://data.sec.gov/test"), {"ok": True})

    def test_transient_http_error_is_retried(self):
        transport = FakeTransport([
            {"status": 503, "headers": {}, "body": b"busy"},
            {"status": 200, "headers": {}, "body": b'{"ok": true}'},
        ])
        client = SecHttpClient(user_agent="test", transport=transport, retries=1, backoff_seconds=0)
        self.assertEqual(client.get_json("https://data.sec.gov/test"), {"ok": True})
        self.assertEqual(len(transport.calls), 2)

    def test_non_transient_http_error_is_not_retried(self):
        transport = FakeTransport([{"status": 404, "headers": {}, "body": b"missing"}])
        client = SecHttpClient(user_agent="test", transport=transport, retries=3, backoff_seconds=0)
        with self.assertRaises(SecHttpError):
            client.get_json("https://data.sec.gov/test")
        self.assertEqual(len(transport.calls), 1)

    def test_transport_failure_becomes_sec_http_error_after_retries(self):
        transport = FakeTransport([TimeoutError("timeout"), TimeoutError("timeout")])
        client = SecHttpClient(user_agent="test", transport=transport, retries=1, backoff_seconds=0)
        with self.assertRaises(SecHttpError):
            client.get_json("https://data.sec.gov/test")
        self.assertEqual(len(transport.calls), 2)


if __name__ == "__main__":
    unittest.main()
