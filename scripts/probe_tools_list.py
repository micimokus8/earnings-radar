#!/usr/bin/env python3
"""List available TVRemix MCP tool names."""

from __future__ import annotations

import json

from earnings_monitor.tvremix_http import request_json
from earnings_monitor.wiring import build_tvremix_session


def main() -> None:
    session = build_tvremix_session(secret_path="tvremix API.txt")
    session._initialize()
    response, _ = session._request("tools/list", {})
    tools = ((response or {}).get("result") or {}).get("tools") or []
    print("count:", len(tools))
    for tool in tools:
        name = tool.get("name", "")
        desc = (tool.get("description") or "").split("\n")[0][:80]
        print(f"- {name}: {desc}")


if __name__ == "__main__":
    main()

      
