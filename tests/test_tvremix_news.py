import json
import unittest

from earnings_monitor.tvremix_news import parse_tvremix_news_response


def mcp_payload(payload):
    return {"result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}


class TvremixNewsTests(unittest.TestCase):
    def test_parses_verified_headlines_shape(self):
        result = parse_tvremix_news_response(mcp_payload({
            "success": True,
            "data": {"count": 1, "headlines": [{
                "id": "n1", "title": "Company reports results", "published": "2026-08-13T10:00:00+00:00",
                "provider": "Example", "link": "https://example.test/n1", "story_path": "", "urgency": 0,
            }]},
        }))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["headlines"][0]["headline"], "Company reports results")
        self.assertEqual(result["headlines"][0]["published"], "2026-08-13T10:00:00+00:00")

    def test_invalid_or_missing_headlines_are_unknown(self):
        self.assertEqual(parse_tvremix_news_response({})["status"], "UNKNOWN")
        self.assertEqual(parse_tvremix_news_response(mcp_payload({"success": True, "data": {"headlines": [{"title": "x"}]}}))["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

