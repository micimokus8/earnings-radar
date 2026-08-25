import unittest

from earnings_monitor.tvremix_http import request_json


class _FlakyOpener:
    """Opener that fails first N 429s then succeeds."""

    def __init__(self, failures, status_after=200, body=b'{"ok":1}'):
        self.failures = failures
        self.calls = 0
        self._status_after = status_after
        self._body = body

    def __call__(self, request, timeout=20):
        self.calls += 1
        body = self._body
        class Resp:
            status = self._status_after
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self):
                return body
        if self.calls <= self.failures:
            resp = Resp()
            resp.status = 429
            return resp
        if self._status_after in (429, 500, 502, 503, 504):
            # simulate raised HTTPError for transient status in success path
            import urllib.error
            raise urllib.error.HTTPError(request.full_url, self._status_after,
                                         "e", {}, None)
        return Resp()


class RequestJsonRetryTests(unittest.TestCase):
    def test_retries_on_429_then_succeeds(self):
        opener = _FlakyOpener(failures=2)
        result = request_json(
            "https://x", {}, 20, {"a": 1},
            opener=opener,
            retries=3, backoff_seconds=0.0,
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(opener.calls, 3)

    def test_gives_up_after_retries(self):
        opener = _FlakyOpener(failures=99)
        with self.assertRaises(RuntimeError):
            request_json(
                "https://x", {}, 10, {"a": 1},
                opener=opener, retries=2, backoff_seconds=0.0,
            )

    def test_non_transient_status_not_retried(self):
        opener = _FlakyOpener(failures=0, status_after=403)
        with self.assertRaisesRegex(RuntimeError, "tvremix_http_403"):
            request_json(
                "https://x", {}, 10, {"a": 1},
                opener=opener, retries=3, backoff_seconds=0.0,
            )
        self.assertEqual(opener.calls, 1)


if __name__ == "__main__":
    unittest.main()