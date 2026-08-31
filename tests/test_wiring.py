import tempfile
import unittest
from pathlib import Path

from earnings_monitor.pipeline import EarningsPipeline
from earnings_monitor.alternative_sources import (
    FinnhubNewsClient,
    FinnhubQuoteClient,
    StaticCalendarClient,
    TwelveDataTechnicalClient,
)
from earnings_monitor.wiring import (
    TechnicalScoreAdapter,
    build_default_pipeline,
    load_optional_text,
)


class _StubTechnicals:
    def get(self, symbol):
        bars = [{"t": i, "o": 1, "h": 1, "l": 1, "c": float(i + 1), "v": 1}
                for i in range(60)]
        return {
            "status": "PASS",
            "technicals": {
                "1D": {"price": 100.0, "rsi": 42.0},
                "4h": {"price": 100.0},
            },
            "ohlcv": {"1D": {"status": "PASS", "bars": bars, "symbol": "X", "interval": "1D"},
                      "4h": {"status": "PASS", "bars": bars, "symbol": "X", "interval": "4h"}},
        }


class WiringTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.tv_secret = base / "tv.txt"
        self.tv_secret.write_text("tv-token")
        self.fh_key = base / "fh.txt"
        self.fh_key.write_text("fh-token")

    def tearDown(self):
        self._tmp.cleanup()

    def test_technical_adapter_maps_to_score_values(self):
        adapter = TechnicalScoreAdapter(_StubTechnicals())
        result = adapter.get("NASDAQ:AAPL")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["unknown"], [])
        self.assertEqual(result["values"]["price_1d"], 100.0)
        self.assertEqual(result["values"]["rsi_1d"], 42.0)
        self.assertIsNotNone(result["values"]["ema20_1d"])
        self.assertIsNotNone(result["values"]["adx_1d"])

    def test_load_optional_text_returns_none_for_missing_file(self):
        self.assertIsNone(load_optional_text("/nonexistent/ua.txt"))

    def test_builds_pipeline_with_real_clients(self):
        pipeline = build_default_pipeline(
            tvremix_secret_path=str(self.tv_secret),
            finnhub_key_path=str(self.fh_key),
        )
        self.assertIsInstance(pipeline, EarningsPipeline)
        self.assertIsInstance(pipeline.calendar, StaticCalendarClient)
        # TVRemix is primary; free providers remain attached as fallbacks.
        self.assertEqual(type(pipeline.quotes).__name__, "QuotePrimaryFallback")
        self.assertEqual(type(pipeline.forecasts).__name__, "ForecastPrimaryFallback")
        self.assertEqual(type(pipeline.news).__name__, "NewsPrimaryFallback")
        self.assertEqual(type(pipeline.technicals).__name__, "TechnicalPrimaryFallback")
        self.assertIsNotNone(pipeline.symbol_resolver)
        self.assertIsInstance(pipeline.quotes.fallback, FinnhubQuoteClient)
        self.assertIsInstance(pipeline.news.fallback, FinnhubNewsClient)
        self.assertIsInstance(pipeline.technicals.fallback, TwelveDataTechnicalClient)
        # Without SEC user-agent file the SEC lookups stay disabled -> UNKNOWN states.
        self.assertIsNone(pipeline.insider)
        self.assertIsNone(pipeline.dilution)

    def test_enables_sec_lookups_when_user_agent_present(self):
        ua_path = Path(self._tmp.name) / "ua.txt"
        ua_path.write_text("Research contact@example.com")
        pipeline = build_default_pipeline(
            tvremix_secret_path=str(self.tv_secret),
            finnhub_key_path=str(self.fh_key),
            sec_user_agent_path=str(ua_path),
        )
        self.assertIsNotNone(pipeline.insider)
        self.assertIsNotNone(pipeline.dilution)


if __name__ == "__main__":
    unittest.main()

      
