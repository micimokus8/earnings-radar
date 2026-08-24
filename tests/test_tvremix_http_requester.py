import json
import unittest

from earnings_monitor.tvremix_http import request_json


class TvremixHttpTests(unittest.TestCase):
    def test_request_json_posts_payload_and_returns_headers(self):
        calls = []

        class Response:
            status = 200
            headers = {"mcp-session-id": "session-2"}

            def read(self):
                return b'{"result":{"ok":true}}'

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def opener(request, timeout):
            calls.append((request, timeout))
            return Response()

        result = request_json(
            "https://example.test/mcp",
            {"Authorization": "Bearer token"},
            7,
            {"jsonrpc": "2.0", "method": "initialize"},
            opener=opener,
        )

        self.assertEqual(result["status"], 200)
        self.assertEqual(result["response"], {"result": {"ok": True}})
        self.assertEqual(result["headers"]["mcp-session-id"], "session-2")
        self.assertEqual(calls[0][1], 7)
        self.assertEqual(calls[0][0].get_method(), "POST")
        self.assertEqual(json.loads(calls[0][0].data), {"jsonrpc": "2.0", "method": "initialize"})

    def test_http_error_is_raised(self):
        class Response:
            status = 401
            headers = {}

            def read(self):
                return b'{"error":"unauthorized"}'

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with self.assertRaises(RuntimeError):
            request_json("https://example.test/mcp", {}, 3, {}, opener=lambda *_args, **_kwargs: Response())


if __name__ == "__main__":
    unittest.main()