#!/usr/bin/env python3
"""Inventory authenticated TVRemix MCP tools without secrets or payloads."""
from __future__ import annotations

import json
from earnings_monitor.wiring import build_tvremix_session


def main() -> int:
    session = build_tvremix_session(secret_path="tvremix API.txt")
    if not session._initialize():
        print(json.dumps({"status": "UNKNOWN", "error": "initialize_failed"}))
        return 1
    response, _ = session._request("tools/list", {})
    tools = ((response or {}).get("result") or {}).get("tools") or []
    rows = []
    for tool in tools:
        schema = tool.get("inputSchema") or {}
        props = schema.get("properties") or {}
        name = str(tool.get("name") or "")
        text = f"{name} {tool.get('description') or ''}".lower()
        relevant = any(word in text for word in ("analyst", "forecast", "estimate", "target", "short", "interest"))
        rows.append({
            "name": name,
            "relevant": relevant,
            "description": str(tool.get("description") or "")[:220],
            "required": schema.get("required", []),
            "input_keys": sorted(props),
        })
    print(json.dumps({"status": "PASS", "tool_count": len(rows), "tools": rows}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
