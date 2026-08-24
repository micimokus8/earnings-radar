"""Normalize the verified TVRemix get_news response."""

from __future__ import annotations

import json


_REQUIRED = ("title", "published")


def _unwrap_mcp(response):
    if not isinstance(response, dict):
        return None
    result = response.get("result")
    content = result.get("content") if isinstance(result, dict) else None
    if not isinstance(content, list) or not content:
        return response
    first = content[0]
    text = first.get("text") if isinstance(first, dict) else None
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_tvremix_news_response(response) -> dict:
    payload = _unwrap_mcp(response)
    data = payload.get("data") if isinstance(payload, dict) else None
    headlines = data.get("headlines") if isinstance(data, dict) else None
    if not isinstance(headlines, list):
        return {"status": "UNKNOWN", "headlines": [], "error": "headlines_missing"}

    normalized = []
    for item in headlines:
        if not isinstance(item, dict) or any(not isinstance(item.get(field), str) for field in _REQUIRED):
            return {"status": "UNKNOWN", "headlines": [], "error": "headline_fields_invalid"}
        normalized.append({
            "headline": item["title"],
            "published": item["published"],
            "provider": item.get("provider"),
            "link": item.get("link"),
            "urgency": item.get("urgency"),
            "id": item.get("id"),
        })
    return {"status": "PASS", "headlines": normalized}


__all__ = ["parse_tvremix_news_response"]

        
