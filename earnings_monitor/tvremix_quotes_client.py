"""TVRemix batch quote client using the verified MCP tool contract."""

from __future__ import annotations

from earnings_monitor.tvremix_quotes import parse_tvremix_quotes_response


class TvremixQuotesClient:
    def __init__(self, session):
        self.session = session

    def get(self, symbols):
        result = self.session.call_tool("get_quotes_batch", {"symbols": symbols})
        if result.get("status") != "PASS":
            return {"status": "UNKNOWN", "quotes": {}, "error": result.get("error")}
        return parse_tvremix_quotes_response(result.get("response"))


__all__ = ["TvremixQuotesClient"]

