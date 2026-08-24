#!/usr/bin/env python3
"""Compare calendar argument variants around a known earnings date."""

from __future__ import annotations

from earnings_monitor.wiring import build_tvremix_session

BASE = {"market": "america", "date_from": "2026-09-28",
        "date_to": "2026-10-02", "limit": 50}


def main() -> None:
    session = build_tvremix_session(secret_path="tvremix API.txt")
    variants = {
        "no_symbols_key": dict(BASE),
        "symbols_null": {**BASE, "symbols": None},
        "symbols_empty": {**BASE, "symbols": []},
    }
    for label, arguments in variants.items():
        result = session.call_tool("get_earnings_calendar", arguments)
        events = []
        if result.get("status") == "PASS":
            response = result.get("response") or {}
            content = ((response.get("result") or {}).get("content") or [{}])[0]
            try:
                import json as _json
                data = _json.loads(content.get("text", "{}"))
                inner = data.get("data") or {}
                events = inner.get("earnings") or data.get("results") or []
            except Exception as exc:
                print(label, "parse_error", type(exc).__name__)
                continue
        print(f"{label}: status={result.get('status')} "
              f"events={len(events)} error={result.get('error')}")
        if events:
            print("  sample:", [e.get("symbol") for e in events[:6]])


if __name__ == "__main__":
    main()

      
