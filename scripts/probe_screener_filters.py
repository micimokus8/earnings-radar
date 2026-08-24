#!/usr/bin/env python3
"""Learn exact earnings column formats + test filter syntax variants."""

from __future__ import annotations

import json

from earnings_monitor.wiring import build_tvremix_session


def _unwrap(result):
    if result.get("status") != "PASS":
        return {"_status": result.get("status"), "_error": str(result.get("error"))[:120]}
    response = result.get("response") or {}
    content = ((response.get("result") or {}).get("content") or [{}])[0]
    try:
        return json.loads(content.get("text", "{}"))
    except Exception as exc:
        return {"_parse_error": type(exc).__name__}


def main() -> None:
    session = build_tvremix_session(secret_path="tvremix API.txt")

    print("=== ZM + SMTC raw formats")
    for sym in ("NASDAQ:ZM", "NASDAQ:SMTC"):
        data = _unwrap(session.call_tool("get_symbol_data", {
            "symbol": sym,
            "columns": ["earnings_release_next_date", "earnings_release_date",
                         "earnings_release_time"],
        }))
        print(sym, json.dumps(data.get("data", data)))

    today = "2026-08-25"
    variants = {
        "v1_left_right": [{"left": "earnings_release_next_date",
                            "operation": "equal", "right": today}],
        "v2_dict": {"earnings_release_next_date": today},
        "v3_field_value": [{"field": "earnings_release_next_date",
                             "operation": "equal", "value": today}],
    }
    for label, filters in variants.items():
        data = _unwrap(session.call_tool("run_screener", {
            "filters": filters,
            "limit": 10,
            "columns": ["name", "earnings_release_next_date"],
            "sort_by": "market_cap_basic",
        }))
        rows = ((data.get("data") or {}).get("results")) or []
        print(f"{label}: rows={len(rows)} "
              f"symbols={[r.get('symbol') for r in rows[:8]]}")


if __name__ == "__main__":
    main()

      
