#!/usr/bin/env python3
"""Resolve bare earnings tickers through authenticated TVRemix search."""
from __future__ import annotations
import json
import sys
from earnings_monitor.wiring import build_tvremix_session


def main() -> int:
    symbols = sys.argv[1:] or ["CANG", "BLRX", "SAIC"]
    session = build_tvremix_session(secret_path="tvremix API.txt")
    rows = []
    for symbol in symbols:
        result = session.call_tool("search_symbols", {"query": symbol, "limit": 10})
        response = result.get("response") if isinstance(result, dict) else None
        # Print only bounded symbol/name/exchange-like fields, never raw payload.
        data = response.get("result", {}) if isinstance(response, dict) else {}
        content = data.get("content", []) if isinstance(data, dict) else []
        text = content[0].get("text") if content and isinstance(content[0], dict) else ""
        try:
            payload = json.loads(text)
        except (TypeError, ValueError):
            payload = {}
        candidates = payload.get("data", payload.get("results", [])) if isinstance(payload, dict) else []
        if isinstance(candidates, dict):
            candidates = candidates.get("results", [])
        safe = []
        for item in candidates if isinstance(candidates, list) else []:
            if isinstance(item, dict):
                safe.append({k: item.get(k) for k in ("symbol", "name", "exchange", "type") if item.get(k) is not None})
        rows.append({"query": symbol, "transport": result.get("status"), "matches": safe[:10]})
    print(json.dumps(rows, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

