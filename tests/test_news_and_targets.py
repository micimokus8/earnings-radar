import unittest

from earnings_monitor.news import evaluate_news
from earnings_monitor.targets import detect_target_cut


class NewsTests(unittest.TestCase):
    def test_negative_keyword_within_window_is_negative(self):
        result = evaluate_news(
            headlines=[{"headline": "Company announces investigation", "published": "2026-08-10T12:00:00+00:00"}],
            as_of="2026-08-12T12:00:00+00:00",
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["negative_news"])

    def test_old_negative_headline_is_outside_window(self):
        result = evaluate_news(
            headlines=[{"headline": "Company announces investigation", "published": "2026-08-01T12:00:00+00:00"}],
            as_of="2026-08-12T12:00:00+00:00",
        )
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["negative_news"])

    def test_empty_successful_response_is_observed_pass(self):
        result = evaluate_news([], as_of="2026-08-12T12:00:00+00:00")
        self.assertEqual(result["status"], "PASS")

    def test_commission_is_not_a_miss(self):
        result = evaluate_news(
            headlines=[{"headline": "Senate commission permits the review", "published": "2026-08-10T12:00:00+00:00"}],
            as_of="2026-08-12T12:00:00+00:00",
        )
        self.assertFalse(result["negative_news"])
        self.assertIsNone(result["news_severity"])

    def test_word_miss_is_negative_and_permission_is_not(self):
        missed = evaluate_news(
            headlines=[{"headline": "Company misses estimates", "published": "2026-08-10T12:00:00+00:00"}],
            as_of="2026-08-12T12:00:00+00:00",
        )
        permission = evaluate_news(
            headlines=[{"headline": "Company receives export permission", "published": "2026-08-10T12:00:00+00:00"}],
            as_of="2026-08-12T12:00:00+00:00",
        )
        self.assertTrue(missed["negative_news"])
        self.assertFalse(permission["negative_news"])
        self.assertEqual(permission["positive_news_count"], 0)

    def test_failed_request_is_unknown(self):
        result = evaluate_news(None, as_of="2026-08-12T12:00:00+00:00")
        self.assertEqual(result["status"], "UNKNOWN")


class TargetTests(unittest.TestCase):
    def test_target_cut_requires_minimum_change(self):
        result = detect_target_cut(previous_average=100.0, current_average=98.1, minimum_change_pct=2.0)
        self.assertFalse(result["cut"])

    def test_target_cut_is_detected_at_threshold(self):
        result = detect_target_cut(previous_average=100.0, current_average=98.0, minimum_change_pct=2.0)
        self.assertTrue(result["cut"])
        self.assertEqual(result["change_pct"], -2.0)

    def test_missing_target_is_unknown(self):
        result = detect_target_cut(previous_average=None, current_average=98.0, minimum_change_pct=2.0)
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
