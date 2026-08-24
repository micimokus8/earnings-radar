"""TVRemix client for the verified get_news tool."""

from __future__ import annotations

from earnings_monitor.tvremix_news import parse_tvremix_news_response


class TvremixNewsClient:
    def __init__(self, session, limit: int = 10):
        self.session = session
        self.limit = limit

    def get(self, symbol: str, *, limit: int | None = None) -> dict:
        requested_limit = self.limit if limit is None else limit
        result = self.session.call_tool(
            "get_news", {"symbol": symbol, "limit": requested_limit}
        )
        if result.get("status") != "PASS":
            return {"status": "UNKNOWN", "headlines": [], "error": result.get("error")}
        return parse_tvremix_news_response(result.get("response"))


__all__ = ["TvremixNewsClient"]

