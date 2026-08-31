#!/usr/bin/env python3
"""Summarize the real TVRemix forecast schema without dumping raw payloads."""
from __future__ import annotations

import json
import sys
from collections.abc import Mapping

from earnings_monitor.wiring import build_tvremix_session


def summarize(value, depth=0):
    if depth > 4:
        return type(value).__name__
    if isinstance(value, Mapping):
        return {str(k): summarize(v, depth + 1) for k, v in list(value.items())[:80]}
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "item": summarize(value[0], depth + 1) if value else None}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return {"type": type(value).__name__, "value": value if not isinstance(value, str) or len(value) < 120 else value[:117] + "..."}
    return type(value).__name__


def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "NASDAQ:CANG"
    session = build_tvremix_session(secret_path="tvremix API.txt")
    result = session.call_tool("get_forecasts", {"symbol": symbol})
    response = result.get("response") if isinstance(result, dict) else None
    print(json.dumps({
        "symbol": symbol,
        "transport": result.get("status") if isinstance(result, dict) else None,
        "transport_error": result.get("error") if isinstance(result, dict) else "invalid_result",
        "response_schema": summarize(response),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
