#!/usr/bin/env python3
"""Learn screener column names/format via ZM + basic screener rows."""

from __future__ import annotations

import json

from earnings_monitor.wiring import build_tvremix_session


def _unwrap(result):
    if result.get("status") != "PASS":
        return {"_status": result.get("status"), "_error": result.get("error")}
    response = result.get("response") or {}
    content = ((response.get("result") or {}).get("content") or [{}])[0]
    try:
        return json.loads(content.get("text", "{}"))
    except Exception:
        return {"_raw": str(content)[:300]}


def main() -> None:
    session = build_tvremix_session(secret_path="tvremix API.txt")

    print("=== get_symbol_data NASDAQ:ZM")
    data = _unwrap(session.call_tool("get_symbol_data", {
        "symbol": "NASDAQ:ZM",
        "columns": ["earnings_date", "earnings_release_time",
                     "earnings_per_share_forecast_next", "market_cap_basic", "name"],
    }))
    print(json.dumps(data, indent=2)[:1200])

    print("\n=== run_screener no-filter limit=3")
    data = _unwrap(session.call_tool("run_screener", {"limit": 3}))
    print(json.dumps(data, indent=2)[:1500])


if __name__ == "__main__":
    main()

      
