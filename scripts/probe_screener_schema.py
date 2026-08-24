#!/usr/bin/env python3
"""Dump complete input schemas for screener-related tools."""

from __future__ import annotations

import json

from earnings_monitor.wiring import build_tvremix_session


def main() -> None:
    wanted = {"run_screener", "get_symbol_data"}
    session = build_tvremix_session(secret_path="tvremix API.txt")
    session._initialize()
    response, _ = session._request("tools/list", {})
    tools = ((response or {}).get("result") or {}).get("tools") or []
    for tool in tools:
        if tool.get("name") in wanted:
            print("=" * 25, tool["name"])
            print(json.dumps(tool.get("inputSchema", {}), indent=2))
            print()


if __name__ == "__main__":
    main()

      
