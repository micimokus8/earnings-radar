#!/usr/bin/env python3
"""Filter diagnosis round 2: string-equal control, epoch dates, sort probe."""

from __future__ import annotations

from datetime import datetime, timezone

from earnings_monitor.wiring import build_tvremix_session


def _run(session, arguments):
    result = session.call_tool("run_screener", arguments)
    if result.get("status") != "PASS":
        return f"_ERR {str(result.get('error'))[:80]}"
    response = result.get("response") or {}
    content = ((response.get("result") or {}).get("content") or [{}])[0]
    try:
        import json as _json
        data = _json.loads(content.get("text", "{}"))
        rows = ((data.get("data") or {}).get("results")) or []
        return [(r.get("symbol"), r.get("earnings_release_next_date"))
                for r in rows[:6]]
    except Exception as exc:
        return f"_PARSE {type(exc).__name__}"


def main() -> None:
    session = build_tvremix_session(secret_path="tvremix API.txt")
    d = "2026-08-25"
    epoch_s = int(datetime(2026, 8, 25, tzinfo=timezone.utc).timestamp())
    cols = ["name", "earnings_release_next_date"]

    tests = {
        "A_string_equal_subtype": (
            {"filters": [{"left": "subtype", "operation": "equal",
                          "right": "common"}], "limit": 5, "columns": ["name"]}),
        f"B_epoch_s_{epoch_s}": (
            {"filters": [{"left": "earnings_release_next_date",
                          "operation": "equal", "right": epoch_s}],
             "limit": 5, "columns": cols}),
        "C_compact_20260825": (
            {"filters": [{"left": "earnings_release_next_date",
                          "operation": "equal", "right": "20260825"}],
             "limit": 5, "columns": cols}),
        "D_sort_by_date_asc": (
            {"sort_by": "earnings_release_next_date", "sort_order": "asc",
             "limit": 8, "columns": cols}),
    }
    for label, args in tests.items():
        print(f"{label}: {_run(session, args)}")


if __name__ == "__main__":
    main()

      
