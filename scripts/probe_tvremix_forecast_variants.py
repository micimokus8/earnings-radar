#!/usr/bin/env python3
"""Compare TVRemix forecast symbol variants without printing raw payloads."""
from __future__ import annotations

import json
import sys

from earnings_monitor.tvremix_forecasts import parse_tvremix_forecast_response
from earnings_monitor.wiring import build_tvremix_session


def main() -> int:
    symbols = sys.argv[1:] or ["BLRX", "NASDAQ:BLRX", "NASDAQCM:BLRX", "SAIC", "NYSE:SAIC"]
    session = build_tvremix_session(secret_path="tvremix API.txt")
    for symbol in symbols:
        result = session.call_tool("get_forecasts", {"symbol": symbol})
        parsed = parse_tvremix_forecast_response(result.get("response"), price=1.0)
        forecast = parsed.get("forecast") if isinstance(parsed, dict) else None
        if not isinstance(forecast, dict):
            forecast = {}
        present = sorted(k for k in ("eps_estimate", "target_average", "target_upside_pct", "analyst_rating") if forecast.get(k) is not None)
        print(json.dumps({
            "symbol": symbol,
            "transport": result.get("status"),
            "transport_error": result.get("error"),
            "parsed": parsed.get("status") if isinstance(parsed, dict) else None,
            "fields_present": present,
            "missing": forecast.get("missing", []),
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
