import json
import unittest


def json_bytes(value):
    return json.dumps(value).encode("utf-8")


from earnings_monitor.alternative_sources import (
    FinnhubQuoteClient,
    FinnhubForecastClient,
    FinnhubNewsClient,
    TwelveDataTechnicalClient,
    StaticCalendarClient,
)


class FakeRequester:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def __call__(self, url, *, headers, timeout):
        self.calls.append(url)
        for needle, payload in self.payloads.items():
            if needle in url:
                return {"status": 200, "body": payload}
        return {"status": 404, "body": b"{}"}


class AlternativeSourceTests(unittest.TestCase):
    def test_finnhub_quote_maps_price_and_market_cap(self):
        requester = FakeRequester({
            "/quote?": b'{"c":123.4}',
            "/stock/profile2?": b'{"ticker":"AAPL","name":"Apple","mktCap":3000000}',
        })
        result = FinnhubQuoteClient(key="test", requester=requester).get(["NASDAQ:AAPL"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["quotes"]["NASDAQ:AAPL"]["price"], 123.4)
        self.assertEqual(result["quotes"]["NASDAQ:AAPL"]["market_cap"], 3000000000000)

    def test_forecast_maps_target_eps_and_rating(self):
        requester = FakeRequester({
            "price-target": b'{"targetMean":150}',
            "recommendation": b'[{"buy":5,"strongBuy":2,"hold":1,"sell":0,"strongSell":0}]',
            "eps-estimate": b'{"data":[{"epsAvg":2.5}]}',
        })
        result = FinnhubForecastClient(key="test", requester=requester).get("AAPL", price=100)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["forecast"]["target_upside_pct"], 50.0)
        self.assertEqual(result["forecast"]["eps_estimate"], 2.5)
        self.assertEqual(result["forecast"]["rating_buy"], 7)

    def test_news_empty_is_unknown_not_known_positive(self):
        requester = FakeRequester({"company-news": b"[]"})
        result = FinnhubNewsClient(
            key="test", requester=requester,
            fallback_requester=lambda *args, **kwargs: {"status": 404, "body": b""},
        ).get("AAPL", as_of="2026-08-28T12:00:00+00:00")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["negative_news"])

    def test_news_falls_back_to_yahoo_rss_titles(self):
        requester = FakeRequester({"company-news": b"[]"})
        rss = b"<rss><channel><item><title>Company beats earnings expectations</title><link>https://example.test/a</link></item></channel></rss>"
        result = FinnhubNewsClient(
            key="test", requester=requester,
            fallback_requester=lambda *args, **kwargs: {"status": 200, "body": rss},
        ).get("AAPL", as_of="2026-08-28T12:00:00+00:00")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["source"], "yahoo_rss")
        self.assertEqual(result["headlines"][0]["headline"], "Company beats earnings expectations")

    def test_twelve_data_builds_existing_indicator_shape(self):
        values = [{"open": str(10 + i), "high": str(11 + i), "low": str(9 + i), "close": str(10 + i), "volume": "1000"} for i in range(60)]
        requester = FakeRequester({"time_series?": json_bytes({"values": values})})
        result = TwelveDataTechnicalClient(key="test", requester=requester).get("AAPL")
        self.assertEqual(result["status"], "PASS")
        self.assertIsNotNone(result["values"]["ema20_1d"])
        self.assertIsNotNone(result["values"]["ema50_1d"])
        self.assertIsNotNone(result["values"]["adx_1d"])
        self.assertIsNotNone(result["values"]["macd_1d"])
        self.assertIsNotNone(result["values"]["macd_signal_1d"])

    def test_calendar_is_explicit_unknown_timing_but_pass(self):
        result = StaticCalendarClient().get(symbols=["AAPL"], date_from=None, date_to=None)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["events"][0]["symbol"], "AAPL")
        self.assertEqual(result["events"][0]["timing"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
