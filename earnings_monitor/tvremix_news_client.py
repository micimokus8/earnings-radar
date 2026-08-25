"""TVRemix client for the verified get_news tool.

Fetches raw headlines and *evaluates* them for negative-news signals so the
candidate score's ④ category can actually use ``negative_news`` (previously the
client returned only parsed headlines, so ``negative_news`` was always ``None``
and ④ scored 0 for every symbol).
"""

from __future__ import annotations

from earnings_monitor.news import evaluate_news
from earnings_monitor.tvremix_news import parse_tvremix_news_response

_DEFAULT_WINDOW_DAYS = 7


class TvremixNewsClient:
    def __init__(self, session, limit: int = 10, window_days: int = _DEFAULT_WINDOW_DAYS):
        self.session = session
        self.limit = limit
        self.window_days = window_days

    def get(self, symbol: str, *, limit: int | None = None, as_of: str | None = None) -> dict:
        requested_limit = self.limit if limit is None else limit
        result = self.session.call_tool(
            "get_news", {"symbol": symbol, "limit": requested_limit}
        )
        if result.get("status") != "PASS":
            return {
                "status": "UNKNOWN",
                "headlines": [],
                "negative_news": None,
                "matches": [],
                "error": result.get("error"),
            }
        parsed = parse_tvremix_news_response(result.get("response"))
        if parsed["status"] != "PASS":
            return {
                "status": "UNKNOWN",
                "headlines": [],
                "negative_news": None,
                "matches": [],
                "error": parsed.get("error"),
            }

        headlines = parsed["headlines"]
        if as_of is None:
            # No reference time for the negative-news window: data is present but
            # not time-evaluable here, so treat as "no negative news observed".
            return {
                "status": "PASS",
                "headlines": headlines,
                "negative_news": False,
                "matches": [],
            }

        evaluation = evaluate_news(headlines, as_of=as_of, window_days=self.window_days)
        return {
            # ``status`` reflects data availability; sentiment lives in
            # ``negative_news`` (so scoring can still flag risk without
            # mislabeling a successful fetch as a failure).
            "status": "PASS",
            "headlines": headlines,
            "negative_news": evaluation["negative_news"],
            "matches": evaluation.get("matches", []),
        }


__all__ = ["TvremixNewsClient"]
