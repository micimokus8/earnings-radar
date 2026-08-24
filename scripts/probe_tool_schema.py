#!/usr/bin/env python3
"""Print full input schema for selected TVRemix tools."""

from __future__ import annotations

import json

from earnings_monitor.wiring import build_tvremix_session


def main() -> None:
    wanted = {"run_screener", "get_earnings_calendar"}
    session = build_tvremix_session(secret_path="tvremix API.txt")
    session._initialize()
    response, _ = session._request("tools/list", {})
    tools = ((response or {}).get("result") or {}).get("tools") or []
    for tool in tools:
        if tool.get("name") in wanted:
            print("=" * 20, tool["name"])
            print(json.dumps(tool.get("inputSchema", {}), indent=2)[:3500])
            print("DESC:", (tool.get("description") or ""))


if __name__ == "__main__":
    main()

      
