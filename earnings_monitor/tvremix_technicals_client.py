"""TVRemix clients for verified technicals and OHLCV tools."""

from __future__ import annotations

from earnings_monitor.tvremix_technicals import (
    parse_tvremix_ohlcv_response,
    parse_tvremix_technicals_response,
)


class TvremixTechnicalsClient:
    def __init__(self, session, ohlcv_count: int = 300):
        self.session = session
        self.ohlcv_count = ohlcv_count

    def get(self, symbol: str, *, ohlcv_count: int | None = None) -> dict:
        count = self.ohlcv_count if ohlcv_count is None else ohlcv_count
        technicals = {}
        ohlcv = {}
        errors = []

        for interval in ("1D", "4h"):
            response = self.session.call_tool(
                "get_technicals", {"symbol": symbol, "interval": interval}
            )
            if response.get("status") != "PASS":
                errors.append(f"technicals_{interval}")
                continue
            parsed = parse_tvremix_technicals_response(response.get("response"))
            technicals[interval] = parsed.get("technicals")
            if parsed.get("status") != "PASS":
                errors.append(f"technicals_{interval}")

        for interval in ("1D", "4h"):
            response = self.session.call_tool(
                "get_ohlcv",
                {
                    "symbol": symbol,
                    "interval": interval,
                    "count": count,
                    "summary": False,
                },
            )
            if response.get("status") != "PASS":
                errors.append(f"ohlcv_{interval}")
                continue
            parsed = parse_tvremix_ohlcv_response(response.get("response"))
            ohlcv[interval] = parsed
            if parsed.get("status") != "PASS":
                errors.append(f"ohlcv_{interval}")

        if errors:
            return {
                "status": "UNKNOWN",
                "technicals": technicals,
                "ohlcv": ohlcv,
                "errors": errors,
            }
        return {"status": "PASS", "technicals": technicals, "ohlcv": ohlcv}


__all__ = ["TvremixTechnicalsClient"]

