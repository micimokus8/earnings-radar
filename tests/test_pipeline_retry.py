import unittest

from earnings_monitor.pipeline import EarningsPipeline


class _Flaky:
    def __init__(self, failures):
        self._failures = failures
        self.attempts = 0

    def get(self, symbol, **kwargs):
        self.attempts += 1
        if self.attempts <= self._failures:
            raise RuntimeError("transient")
        return {"status": "PASS", "negative_news": False}


class _UnknownThenPass(_Flaky):
    def get(self, symbol, **kwargs):
        self.attempts += 1
        if self.attempts <= self._failures:
            return {"status": "UNKNOWN"}
        return {"status": "PASS", "negative_news": False}


class _Static:
    def get(self, *args, **kwargs):
        return {"status": "PASS", "events": []}


class PipelineRetryTests(unittest.TestCase):
    def _pipeline(self, news_client, **kwargs):
        sleeps = []
        defaults = dict(
            calendar=_Static(), quotes=_Static(), forecasts=_Static(),
            technicals=_Static(), news=news_client,
            short_interest=_Static(),
            sleep=sleeps.append,
        )
        defaults.update(kwargs)
        return EarningsPipeline(**defaults), sleeps

    def test_transient_exception_retried_until_success(self):
        client = _Flaky(failures=1)
        pipeline, sleeps = self._pipeline(client)
        result = pipeline.run(["NASDAQ:AAPL"], as_of="2026-08-24T16:30:00+00:00")
        self.assertEqual(result["candidates"][0]["sources"]["news"]["status"], "PASS")
        self.assertEqual(client.attempts, 2)
        self.assertEqual(len(sleeps), 1)

    def test_unknown_result_retried_until_success(self):
        client = _UnknownThenPass(failures=1)
        pipeline, sleeps = self._pipeline(client)
        result = pipeline.run(["NASDAQ:AAPL"], as_of="2026-08-24T16:30:00+00:00")
        self.assertEqual(result["candidates"][0]["sources"]["news"]["status"], "PASS")
        self.assertEqual(client.attempts, 2)

    def test_permanent_unknown_stops_after_all_attempts(self):
        client = _UnknownThenPass(failures=99)
        pipeline, sleeps = self._pipeline(client, retries=2, backoff_seconds=0.0)
        result = pipeline.run(["NASDAQ:AAPL"], as_of="2026-08-24T16:30:00+00:00")
        self.assertEqual(result["candidates"][0]["sources"]["news"]["status"],
                         "UNKNOWN")
        self.assertEqual(client.attempts, 3)


if __name__ == "__main__":
    unittest.main()

      
