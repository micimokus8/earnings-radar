#!/usr/bin/env python3
"""Inspect only the bounded structural shape of TVRemix symbol search."""
from __future__ import annotations
import json
from earnings_monitor.wiring import build_tvremix_session


def shape(value, depth=0):
    if depth > 5:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): shape(v, depth + 1) for k, v in list(value.items())[:30]}
    if isinstance(value, list):
        return {"type":"list", "len":len(value), "first":shape(value[0], depth+1) if value else None}
    if isinstance(value, str):
        return {"type":"str", "value":value[:160]}
    return {"type":type(value).__name__, "value":value}

s=build_tvremix_session(secret_path="tvremix API.txt")
r=s.call_tool("search_symbols", {"query":"CANG", "limit":10})
print(json.dumps({"transport":r.get("status"), "response":shape(r.get("response"))}, sort_keys=True))

for sym in ("NASDAQ:CANG", "NYSE:CANG", "NASDAQ:BLRX", "NASDAQ:SAIC", "NYSE:SAIC"):
    r=s.call_tool("get_forecasts", {"symbol":sym})
    print(json.dumps({"symbol":sym,"transport":r.get("status"),"response":shape(r.get("response"))}, sort_keys=True))
