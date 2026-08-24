#!/usr/bin/env python3
"""Isolate screener filter syntax: numeric control vs date variants."""

from __future__ import annotations

from earnings_monitor.wiring import build_tvremix_session


def _rows(session, filters, limit=8):
    result = session.call_tool("run_screener", {
        "filters": filters, "limit": limit,
        "columns": ["name"], "sort_by": "market_cap_basic",
    })
    if result.get("status") != "PASS":
        return f"_ERR {str(result.get('error'))[:80]}"
    response = result.get("response") or {}
    content = ((response.get("result") or {}).get("content") or [{}])[0]
    try:
        import json as _json
        data = _json.loads(content.get("text", "{}"))
        rows = ((data.get("data") or {}).get("results")) or []
        return [r.get("symbol") for r in rows]
    except Exception as exc:
        return f"_PARSE {type(exc).__name__}"


def main() -> None:
    session = build_tvremix_session(secret_path="tvremix API.txt")
    d = "2026-08-25"
    variants = {
        "control_mcap_above_1e11": [{"left": "market_cap_basic",
                                      "operation": "above", "right": 100000000000}],
        "v4_in_range": [{"left": "earnings_release_next_date",
                          "operation": "in_range", "right": [d, d]}],
        "v5_eq_short": [{"left": "earnings_release_next_date",
                          "operation": "eq", "right": d}],
        "v6_neq_old_date": [{"left": "earnings_release_next_date",
                              "operation": "neq", "right": "1990-01-01"}],
        "v7_above_epoch": [{"left": "earnings_release_next_date",
                             "operation": "above", "right": 1787664000}],
    }
    for label, filters in variants.items():
        print(f"{label}: {_rows(session, filters)}")


if __name__ == "__main__":
    main()

      
