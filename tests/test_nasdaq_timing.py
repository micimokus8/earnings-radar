import unittest

from earnings_monitor.nasdaq_timing import classify_nasdaq_timing


class NasdaqTimingTests(unittest.TestCase):
    def test_pre_market_maps_to_before_open(self):
        self.assertEqual(classify_nasdaq_timing("time-pre-market")["state"], "BEFORE_OPEN")

    def test_after_hours_maps_to_after_close(self):
        self.assertEqual(classify_nasdaq_timing("time-after-hours")["state"], "AFTER_CLOSE")

    def test_not_supplied_is_unknown(self):
        self.assertEqual(classify_nasdaq_timing("time-not-supplied")["state"], "UNKNOWN")

    def test_request_failure_is_unknown(self):
        self.assertEqual(classify_nasdaq_timing(None)["state"], "UNKNOWN")

    def test_unrecognized_value_is_unknown(self):
        self.assertEqual(classify_nasdaq_timing("surprise")["state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
