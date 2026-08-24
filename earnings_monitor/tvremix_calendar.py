from __future__ import annotations

import json


def _unwrap_mcp(response):
    result = response.get("result") if isinstance(response, dict) else None
    content = result.get("content") if isinstance(result, dict) else None
    if not isinstance(content, list) or not content:
        return response
    text = content[0].get("text") if isinstance(content[0], dict) else None
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_tvremix_calendar_response(response) -> dict:
    if not isinstance(response, dict):
        return {"status": "UNKNOWN", "events": [], "error": "invalid_response"}
    response = _unwrap_mcp(response)
    if not isinstance(response, dict):
        return {"status": "UNKNOWN", "events": [], "error": "invalid_response"}
    events = response.get("data", response.get("results"))
    if isinstance(events, dict):
        events = events.get("earnings")
    if not isinstance(events, list):
        return {"status": "UNKNOWN", "events": [], "error": "events_array_missing"}
    normalized = []
    for event in events:
        if not isinstance(event, dict):
            return {"status": "UNKNOWN", "events": [], "error": "invalid_event"}
        normalized.append({
            "symbol": event.get("symbol"),
            "next_earnings_date": event.get("next_earnings_date"),
            "eps_estimate": event.get("eps_estimate"),
            "revenue_estimate": event.get("revenue_estimate"),
        })
    return {"status": "PASS", "events": normalized}


__all__ = ["parse_tvremix_calendar_response"]
