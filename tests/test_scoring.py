import unittest

from earnings_monitor.scoring import WATCH_PCT, STRONG_PCT, label_for, score_candidate


COMPLETE_BASE = {
    "price": 100,
    "eps_estimate": 1.0,
    "ohlcv_1d": "present",
    "market_cap": 3_000_000_000,
    "short_pct_outstanding": 0.0,
    "days_to_cover": 0.0,
    "target_upside_pct": 0.0,
    "target_recently_cut": False,
    "price_1d": 100,
    "ema20_1d": 100,
    "price_4h": 100,
    "ema20_4h": 100,
    "ema50_1d": 100,
    "rsi_1d": 40,
    "adx_1d": 25,
    "news_status": "PASS",
    "negative_news": False,
    "insider_status": "NO_DIRECT_SELL",
    "dilution_status": "NO_DILUTION_FILING_FOUND",
}


class ScoringTests(unittest.TestCase):
    def test_all_positive_rules_total_fourteen_and_strong(self):
        values = {**COMPLETE_BASE,
            "eps_estimate": -0.1,
            "target_upside_pct": 31,
            "target_recently_cut": True,
            "short_pct_outstanding": 16,
            "days_to_cover": 4,
            "price_1d": 98, "ema20_1d": 99,
            "price_4h": 99, "ema20_4h": 100,
            "ema50_1d": 100,
            "rsi_1d": 39, "adx_1d": 24,
            # Chart-Kategorie hat seit dem 52W/5d-Ausbau 5 Punkte — ohne diese
            # Felder bleiben 3 davon "unknown" und der Test war nie erreichbar.
            "distance_to_52w_pct": -35, "change_5d_pct": 2,
        }
        result = score_candidate(values)
        self.assertEqual(result["total_points"], 14)
        self.assertEqual(result["reachable_points"], 14)
        self.assertEqual(result["score_pct"], 100.0)
        self.assertEqual(result["label"], "STRONG_SETUP")
        self.assertEqual(result["state"], "COMPLETE")

    def test_short_thresholds_are_cumulative(self):
        values = {**COMPLETE_BASE, "short_pct_outstanding": 16, "days_to_cover": 4}
        result = score_candidate(values)
        self.assertEqual(result["categories"]["short_interest"]["points"], 3)

    def test_boundary_values_do_not_trigger_strict_greater_rules(self):
        # short_pct 15 erfuellt >3 UND >8 (kumulativ = 2); days 3 erfuellt
        # weder >3 noch >5 (strikt) -> 0. Die alte Erwartung 1 widersprach
        # test_short_thresholds_are_cumulative.
        values = {**COMPLETE_BASE, "short_pct_outstanding": 15, "days_to_cover": 3}
        result = score_candidate(values)
        self.assertEqual(result["categories"]["short_interest"]["points"], 2)

    def test_unknown_news_subcheck_is_partial_and_no_point(self):
        values = {**COMPLETE_BASE, "news_status": "UNKNOWN"}
        result = score_candidate(values)
        category = result["categories"]["news_and_sec"]
        self.assertEqual(category["state"], "PARTIAL")
        self.assertEqual(category["points"], 2)

    def test_no_recent_filing_is_successful_insider_check(self):
        values = {**COMPLETE_BASE, "insider_status": "NO_RECENT_FILING_FOUND"}
        result = score_candidate(values)
        self.assertEqual(result["categories"]["news_and_sec"]["points"], 3)
        self.assertEqual(result["categories"]["news_and_sec"]["state"], "PASS")

    def test_confirmed_dilution_does_not_earn_dilution_point(self):
        values = {**COMPLETE_BASE, "dilution_status": "CONFIRMED_DILUTION"}
        result = score_candidate(values)
        self.assertEqual(result["categories"]["news_and_sec"]["points"], 2)

    def test_missing_core_value_blocks_label_and_marks_incomplete(self):
        values = {**COMPLETE_BASE, "days_to_cover": None}
        result = score_candidate(values)
        self.assertEqual(result["state"], "INCOMPLETE")
        self.assertIsNone(result["label"])
        self.assertFalse(result["final_recommendation_allowed"])

    def test_unsupported_short_interest_is_neutral_na(self):
        # Exchange not covered (e.g. NYSE): short-interest is neutrally excluded,
        # not penalized, and must not inject unknown fields.
        values = {**COMPLETE_BASE,
                  "short_pct_outstanding": None,
                  "days_to_cover": None,
                  "short_interest_supported": False}
        result = score_candidate(values)
        category = result["categories"]["short_interest"]
        self.assertEqual(category["state"], "N/A")
        self.assertEqual(category["points"], 0)
        self.assertEqual(category["unknown"], [])
        # Remaining categories still score normally -> candidate is complete.
        self.assertEqual(result["state"], "COMPLETE")
        self.assertIsNotNone(result["label"])


class NormalisationTests(unittest.TestCase):
    """Score wird auf die erreichbaren Punkte bezogen (NYSE-Short-Interest,
    fehlendes Analysten-Coverage). Datenluecken von UNS zaehlen weiter."""

    def test_structural_na_lowers_the_denominator(self):
        values = {**COMPLETE_BASE, "short_interest_supported": False}
        result = score_candidate(values)
        self.assertEqual(result["reachable_points"], 11)
        self.assertEqual(result["max_points"], 14)
        self.assertAlmostEqual(
            result["score_pct"],
            round(result["total_points"] / 11 * 100, 1),
        )

    def test_our_own_gaps_do_not_lower_the_denominator(self):
        # SEC offline / Kursziel 403: unbekannt, aber KEIN struktureller N/A.
        values = {**COMPLETE_BASE, "news_status": "UNKNOWN",
                  "insider_status": "UNKNOWN", "dilution_status": "UNKNOWN"}
        result = score_candidate(values)
        self.assertEqual(result["reachable_points"], 14)
        self.assertLess(result["score_pct"], 71.4)

    def test_full_house_is_still_fourteen(self):
        result = score_candidate({**COMPLETE_BASE, "target_upside_pct": 31,
                                  "eps_estimate": -1, "analyst_rating": "buy",
                                  "target_recently_cut": True,
                                  "short_pct_outstanding": 16, "days_to_cover": 6,
                                  "distance_to_52w_pct": -35, "change_5d_pct": 2,
                                  "rsi_1d": 30, "price_1d": 98, "ema20_1d": 99})
        self.assertEqual(result["reachable_points"], 14)
        self.assertEqual(result["score_pct"], 100.0)

    def test_label_thresholds(self):
        self.assertEqual(label_for(STRONG_PCT, None), "STRONG_SETUP")
        self.assertEqual(label_for(STRONG_PCT - 0.1, None), "WATCH")
        self.assertEqual(label_for(WATCH_PCT, None), "WATCH")
        self.assertEqual(label_for(WATCH_PCT - 0.1, None), "SKIP")
        self.assertEqual(label_for(100.0, "OVERBOUGHT"), "SKIP (OVERBOUGHT)")

    def test_analyst_points_are_capped_at_category_max(self):
        values = {**COMPLETE_BASE, "target_upside_pct": 40, "eps_estimate": -1,
                  "analyst_rating": "strong buy", "target_recently_cut": True}
        result = score_candidate(values)
        self.assertLessEqual(result["categories"]["analyst_expectation"]["points"], 3)


if __name__ == "__main__":
    unittest.main()
