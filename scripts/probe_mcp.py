#!/usr/bin/env python3
"""Probe TVRemix MCP initialize: what does the server actually return?"""

from __future__ import annotations

import json

from earnings_monitor.tvremix_http import request_json
from earnings_monitor.wiring import build_tvremix_session


def main() -> None:
    session = build_tvremix_session(secret_path="tvremix API.txt")
    status, msg = None, ""
    try:
        ok = session._initialize()
        status = "initialize_ok" if ok else "initialize_failed"
        msg = f"session_id={session.session_id!r}"
    except Exception as exc:
        status = f"exception:{type(exc).__name__}"
        msg = str(exc)[:200]
    print(f"init_status={status}")
    print(msg)

    # Raw transport probe: status + body of initialize via request_json.
    try:
        resp = request_json(
            session.url, session.headers, session.timeout,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                        "clientInfo": {"name": "probe", "version": "0"}}},
        )
        print("raw_status=", resp.get("status"))
        body = resp.get("response")
        print("raw_keys=", list(body.keys()) if isinstance(body, dict) else type(body).__name__)
        print("raw_head=", str(body)[:300])
    except Exception as exc:
        print("raw_exception=", type(exc).__name__, str(exc)[:200])

    try:
        result = session.call_tool("get_quote", {"symbol": "NASDAQ:ZM"})
        print("quote_status=", result.get("status"))
        print("quote_error=", result.get("error"))
    except Exception as exc:
        print("quote_exception=", type(exc).__name__, str(exc)[:200])


if __name__ == "__main__":
    main()