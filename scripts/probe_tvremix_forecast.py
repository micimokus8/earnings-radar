#!/usr/bin/env python3
"""Safe live probe: TVRemix forecast availability without printing credentials."""
from __future__ import annotations

import json
import sys

from earnings_monitor.wiring import build_tvremix_session
from earnings_monitor.tvremix_forecasts import parse_tvremix_forecast_response


def main() -> int:
    symbols = sys.argv[1:] or ["NASDAQ:BLRX", "NYSE:SAIC"]
    session = build_tvremix_session(secret_path="tvremix API.txt")
    for symbol in symbols:
        result = session.call_tool("get_forecasts", {"symbol": symbol})
        response = result.get("response") if isinstance(result, dict) else None
        parsed = parse_tvremix_forecast_response(response, price=1.0)
        forecast = parsed.get("forecast") if isinstance(parsed, dict) else None
        if not isinstance(forecast, dict):
            forecast = {}
        fields = {
            key: forecast.get(key)
            for key in ("eps_estimate", "target_average", "target_upside_pct", "analyst_rating")
            if forecast.get(key) is not None
        }
        print(json.dumps({
            "symbol": symbol,
            "transport_status": result.get("status") if isinstance(result, dict) else None,
            "transport_error": result.get("error") if isinstance(result, dict) else "invalid_result",
            "parsed_status": parsed.get("status") if isinstance(parsed, dict) else None,
            "fields_present": sorted(fields),
            "values": fields,
            "missing": forecast.get("missing", []),
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
