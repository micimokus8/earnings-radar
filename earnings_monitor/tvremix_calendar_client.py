"""TVRemix earnings-calendar client using the verified MCP tool contract."""

from __future__ import annotations

from earnings_monitor.tvremix_calendar import parse_tvremix_calendar_response


class TvremixCalendarClient:
    def __init__(self, session, market: str = "america", limit: int = 50):
        self.session = session
        self.market = market
        self.limit = limit

    def get(self, *, symbols=None, date_from=None, date_to=None):
        arguments = {
            "symbols": symbols,
            "market": self.market,
            "date_from": date_from,
            "date_to": date_to,
            "limit": self.limit,
        }
        result = self.session.call_tool("get_earnings_calendar", arguments)
        if result.get("status") != "PASS":
            return {"status": "UNKNOWN", "events": [], "error": result.get("error")}
        return parse_tvremix_calendar_response(result.get("response"))


__all__ = ["TvremixCalendarClient"]

