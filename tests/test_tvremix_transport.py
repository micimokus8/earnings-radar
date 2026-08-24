import tempfile
import unittest
from pathlib import Path

from earnings_monitor.tvremix_transport import TvremixTransport


class TvremixTransportTests(unittest.TestCase):
    def test_calls_requester_with_bearer_token_and_timeout(self):
        calls = []

        def requester(url, headers, timeout, payload):
            calls.append((url, headers, timeout, payload))
            return {"data": {"ok": True}}

        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "api-key"
            secret.write_text("secret-value\n")
            transport = TvremixTransport(
                secret_path=secret,
                requester=requester,
                timeout=12,
            )
            result = transport.call("https://example.test/mcp", {"name": "tools/list"})

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(calls[0][1]["Authorization"], "Bearer secret-value")
        self.assertEqual(calls[0][2], 12)

    def test_missing_secret_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = TvremixTransport(
                secret_path=Path(directory) / "missing",
                requester=lambda *_: {"data": {}},
            )
            result = transport.call("https://example.test/mcp", {})
        self.assertEqual(result["status"], "UNKNOWN")

    def test_request_error_is_unknown(self):
        def requester(*_args, **_kwargs):
            raise TimeoutError("timed out")

        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "api-key"
            secret.write_text("secret-value")
            transport = TvremixTransport(secret_path=secret, requester=requester)
            result = transport.call("https://example.test/mcp", {})
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

