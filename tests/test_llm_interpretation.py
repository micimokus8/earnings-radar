import unittest

from earnings_monitor.llm_interpretation import build_prompt, interpret_candidates


def _candidates():
    return [{
        "symbol": "NASDAQ:ZM",
        "status": "PASS",
        "missing": [],
        "score": {
            "total_points": 5, "max_points": 14, "label": "SKIP",
            "categories": {
                "analyst_expectation": {"points": 1},
                "short_interest": {"points": 0},
                "chart_confirmation": {"points": 2},
                "news_and_sec": {"points": 2},
            },
        },
        "values": {
            "price": 303.5, "eps_estimate": 1.0, "target_upside_pct": 31.0,
            "target_recently_cut": False, "short_pct_outstanding": 0.96,
            "days_to_cover": 2.42, "price_1d": 300.0, "price_4h": 302.0,
            "ema20_1d": 310.0, "ema50_1d": 295.0, "rsi_1d": 42.0, "adx_1d": 20.0,
            "news_status": "PASS", "negative_news": False,
            "insider_status": "NO_DIRECT_SELL", "dilution_status": "NO_DILUTION_FILING_FOUND",
        },
        "sources": {"calendar": {"earnings_date": "2026-08-25", "earnings_timing": "AFTER_CLOSE"}},
    }]


class _FakeRequester:
    def __init__(self, response="", error=None):
        self._response = response
        self._error = error
        self.calls = []

    def post_json(self, url, *, headers, timeout, payload):
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        if self._error is not None:
            raise self._error
        return {"choices": [{"message": {"content": self._response}}]}


class InterpretationTests(unittest.TestCase):
    def test_prompt_includes_markers_and_facts(self):
        p = build_prompt(_candidates())
        self.assertIn("NASDAQ:ZM", p)
        self.assertIn("DEUTUNG:", p)
        self.assertIn("EMPFEHLUNG:", p)
        self.assertIn("SKIP", p)

    def test_parse_deutung_and_empfehlung(self):
        bot = ("DEUTUNG:NASDAQ:ZM Setup schwach, Ziel klein.\n"
               "EMPFEHLUNG: Heute eher nichts Kaufenswertes.")
        fake = _FakeRequester(bot)
        out = interpret_candidates(
            _candidates(), api_key="k", base_url="https://x", model="m",
            requester=fake.post_json,
        )
        self.assertEqual(out["deutung"].get("NASDAQ:ZM"),
                         "Setup schwach, Ziel klein.")
        self.assertEqual(out["empfehlung"], "Heute eher nichts Kaufenswertes.")

    def test_error_returns_empty_with_error_hint(self):
        fake = _FakeRequester(error=RuntimeError("boom"))
        out = interpret_candidates(
            _candidates(), api_key="k", base_url="https://x", model="m",
            requester=fake.post_json,
        )
        self.assertEqual(out.get("deutung"), {})
        self.assertEqual(out.get("empfehlung"), "")
        self.assertIn("boom", out.get("error", ""))

    def test_empty_response_returns_error_hint(self):
        fake = _FakeRequester("")
        out = interpret_candidates(
            _candidates(), api_key="k", base_url="https://x", model="m",
            requester=fake.post_json,
        )
        self.assertEqual(out.get("deutung"), {})
        self.assertEqual(out.get("empfehlung"), "")
        self.assertTrue(out.get("error"))

    def test_empty_candidates_returns_empty(self):
        out = interpret_candidates(
            [], api_key="k", base_url="https://x", model="m",
            requester=_FakeRequester("").post_json,
        )
        self.assertEqual(out, {"deutung": {}, "empfehlung": ""})


if __name__ == "__main__":
    unittest.main()