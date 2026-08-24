#!/usr/bin/env python3
"""Check screener pagination depth: rows per date at limit=1000."""

from __future__ import annotations

import json
from collections import Counter

from earnings_monitor.wiring import build_tvremix_session


def main() -> None:
    session = build_tvremix_session(secret_path="tvremix API.txt")
    result = session.call_tool("run_screener", {
        "sort_by": "earnings_release_next_date",
        "sort_order": "asc",
        "limit": 1000,
        "columns": ["name", "earnings_release_next_date"],
    })
    if result.get("status") != "PASS":
        print("ERR", result.get("error"))
        return
    response = result.get("response") or {}
    content = ((response.get("result") or {}).get("content") or [{}])[0]
    data = json.loads(content.get("text", "{}"))
    rows = ((data.get("data") or {}).get("results")) or []
    print("total_rows:", len(rows))
    dates = Counter(r.get("earnings_release_next_date") for r in rows)
    for date_key, count in sorted(dates.items(), key=lambda kv: (kv[0] is None, kv[0])):
        print(f"  {date_key}: {count}")
    zm = [r["symbol"] for r in rows if r.get("symbol") in ("NASDAQ:ZM", "NASDAQ:SMTC")]
    print("ZM/SMTC positions:", [(i, r["symbol"]) for i, r in enumerate(rows)
                                  if r.get("symbol") in ("NASDAQ:ZM", "NASDAQ:SMTC")])


if __name__ == "__main__":
    main()

      
