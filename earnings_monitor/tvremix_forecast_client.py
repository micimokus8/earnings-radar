"""TVRemix forecast client using the verified MCP tool contract."""

from __future__ import annotations

from earnings_monitor.tvremix_forecasts import parse_tvremix_forecast_response


class TvremixForecastClient:
    def __init__(self, transport, url: str):
        self.transport = transport
        self.url = url
        self._request_id = 0

    def get(self, symbol: str, *, price: float) -> dict:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {
                "name": "get_forecasts",
                "arguments": {"symbol": symbol},
            },
        }
        if hasattr(self.transport, "call_tool"):
            result = self.transport.call_tool("get_forecasts", {"symbol": symbol})
        else:
            result = self.transport.call(self.url, payload)
        if result.get("status") != "PASS":
            return {"status": "UNKNOWN", "forecast": None, "error": result.get("error")}
        return parse_tvremix_forecast_response(result.get("response"), price=price)


__all__ = ["TvremixForecastClient"]

