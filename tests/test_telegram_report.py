import unittest

from earnings_monitor.report_builder import build_report
from earnings_monitor.telegram_report import render_report


def _sample():
    return build_report(
        report_type="BEFORE_OPEN",
        report_date="2026-08-13",
        as_of="2026-08-13T09:30:00+00:00",
        candidates=[
            {
                "symbol": "NASDAQ:AAPL",
                "status": "PASS",
                "missing": [],
                "values": {
                    "price": 303.5, "eps_estimate": 1.0,
                    "target_upside_pct": 31.0, "target_recently_cut": False,
                    "short_pct_outstanding": 0.96, "days_to_cover": 2.42,
                    "rsi_1d": 41.4, "ema20_1d": 313.0, "ema50_1d": 309.0,
                    "price_1d": 303.0, "price_4h": 304.0, "adx_1d": 22.1,
                    "macd_1d": 1.234, "macd_signal_1d": 1.111, "macd_histogram_1d": 0.123,
                    "negative_news": False,
                    "insider_status": "NO_DIRECT_SELL",
                },
                "score": {
                    "total_points": 10, "max_points": 14, "label": "STRONG_SETUP",
                    "categories": {
                        "analyst_expectation": {"points": 1},
                        "short_interest": {"points": 0},
                        "chart_confirmation": {"points": 5},
                        "news_and_sec": {"points": 4},
                    },
                },
            },
        ],
    )


class TelegramReportTests(unittest.TestCase):
    def test_rich_layout_contains_rows_ranking_and_empfehlung(self):
        text = render_report(
            _sample(),
            deutung={"NASDAQ:AAPL": "Starkes Setup"},
            empfehlung="AAPL ist der Top-Kandidat.",
        )
        self.assertIn("BEFORE OPEN — Earnings 2026-08-13", text)
        self.assertIn("STARKES Setup", text)
        self.assertIn("① Analysten", text)
        self.assertIn("② Short", text)
        self.assertIn("③ Chart", text)
        self.assertIn("④ News/SEC", text)
        self.assertIn("MACD", text)
        self.assertIn("ADX", text)
        self.assertIn("P1D", text)
        self.assertIn("Deutung: Starkes Setup", text)
        self.assertIn("RANKING", text)
        self.assertIn("Meine Empfehlung", text)
        self.assertIn("AAPL ist der", text)

    def test_without_llm_no_deutung_or_empfehlung_blocks(self):
        text = render_report(_sample())
        # PASS candidate with no LLM text -> no empty blocks.
        self.assertNotIn("Deutung:", text)
        self.assertNotIn("Meine Empfehlung", text)

    def test_truncation_when_too_long(self):
        text = render_report(_sample(), max_chars=200)
        self.assertIn("gekürzt", text)


if __name__ == "__main__":
    unittest.main()