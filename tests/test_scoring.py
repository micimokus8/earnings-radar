import unittest

from earnings_monitor.scoring import MAX_POINTS, label_for, score_candidate


def _base(**overrides):
    values = {
        "price": 80.0,
        "price_1d": 80.0,
        "rsi_1d": 55.0,
        "stoch_k_1d": 50.0,
        "high_52w": 100.0,
        "resistance_price": 88.0,
        "news_status": "PASS",
        "negative_news": False,
        "positive_news_count": 0,
        "beat_n": 0,
        "hist_n": 0,
    }
    values.update(overrides)
    return values


class ScoringTests(unittest.TestCase):
    def test_room_points_without_free_analyst_or_news_points(self):
        result = score_candidate(_base(
            eps_estimate=-1.0,
            analyst_rating="buy",
            analyst_revision=None,
            insider_status="NO_RECENT_FILING_FOUND",
            dilution_status="NO_DILUTION_FILING_FOUND",
        ))
        # 20% under the high and 10% under the next pivot: two room points.
        # A buy rating, a negative EPS and "nothing bad happened" add nothing.
        self.assertEqual(result["categories"]["room"]["points"], 2)
        self.assertEqual(result["categories"]["revisions"]["points"], 0)
        self.assertEqual(result["categories"]["news"]["points"], 0)
        self.assertEqual(result["total_points"], 2)
        self.assertEqual(result["max_points"], MAX_POINTS)
        self.assertEqual(result["reachable_points"], MAX_POINTS)
        self.assertIsNone(result["skip_reason"])

    def test_missing_short_interest_does_not_inflate_the_denominator(self):
        bare = score_candidate(_base())
        with_gap = score_candidate(_base(
            short_pct_outstanding=None,
            days_to_cover=None,
            short_interest_supported=False,
        ))
        self.assertEqual(bare["reachable_points"], with_gap["reachable_points"])
        self.assertEqual(bare["score_pct"], with_gap["score_pct"])

    def test_near_high_rsi_and_stochastic_are_hard_blocks(self):
        near = score_candidate(_base(price=98.0, price_1d=98.0, high_52w=100.0))
        self.assertIn("NAHE_52W_HOCH", near["skip_reason"])
        self.assertTrue(near["label"].startswith("SKIP ("))
        hot = score_candidate(_base(rsi_1d=80))
        self.assertIn("RSI_UEBERKAUFT", hot["skip_reason"])
        pinned = score_candidate(_base(stoch_k_1d=95))
        self.assertIn("STOCHASTIK_OBEN", pinned["skip_reason"])

    def test_positive_news_scores_and_silence_does_not(self):
        quiet = score_candidate(_base(positive_news_count=0))
        loud = score_candidate(_base(positive_news_count=2))
        self.assertEqual(quiet["categories"]["news"]["points"], 0)
        self.assertEqual(loud["categories"]["news"]["points"], 2)

    def test_soft_negative_news_is_not_a_buy_and_severe_blocks(self):
        soft = score_candidate(_base(negative_news=True, news_severity="soft", positive_news_count=2))
        self.assertEqual(soft["categories"]["news"]["points"], 0)
        self.assertFalse(str(soft["label"]).startswith("STRONG"))
        severe = score_candidate(_base(negative_news=True, news_severity="severe"))
        self.assertIn("NEWS_NEGATIV", severe["skip_reason"])

    def test_history_and_upward_revision_score_only_when_present(self):
        result = score_candidate(_base(
            beat_n=4, beat_rate=0.75, hist_n=4, hist_reaction_pct=1.5,
            analyst_revision="up", target_revision="up",
        ))
        self.assertEqual(result["categories"]["history"]["points"], 2)
        self.assertEqual(result["categories"]["revisions"]["points"], 2)
        self.assertEqual(result["total_points"], 6)

    def test_target_cut_blocks_instead_of_adding_a_point(self):
        result = score_candidate(_base(target_recently_cut=True, target_revision="down"))
        self.assertEqual(result["categories"]["revisions"]["points"], 0)
        self.assertIn("ERWARTUNG_GESENKT", result["skip_reason"])

    def test_missing_chart_blocks_the_label(self):
        result = score_candidate({"price_1d": 10})
        self.assertEqual(result["state"], "INCOMPLETE")
        self.assertIsNone(result["label"])

    def test_label_helper_stays_watch_while_green_is_disabled(self):
        self.assertEqual(label_for(4, None, technical_points=4, strong_blocked=False), "WATCH")
        self.assertTrue(label_for(4, "NAHE_52W_HOCH", technical_points=4, strong_blocked=False).startswith("SKIP"))


if __name__ == "__main__":
    unittest.main()
