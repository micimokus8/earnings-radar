"""Normalize TVRemix batch quote responses."""

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


def parse_tvremix_quotes_response(response) -> dict:
    if not isinstance(response, dict):
        return {"status": "UNKNOWN", "quotes": {}, "error": "invalid_response"}
    response = _unwrap_mcp(response)
    if not isinstance(response, dict):
        return {"status": "UNKNOWN", "quotes": {}, "error": "invalid_response"}
    quotes = response.get("data")
    if not isinstance(quotes, dict):
        return {"status": "UNKNOWN", "quotes": {}, "error": "quotes_map_missing"}
    if any(not isinstance(symbol, str) or not isinstance(quote, dict) for symbol, quote in quotes.items()):
        return {"status": "UNKNOWN", "quotes": {}, "error": "invalid_quote"}
    return {"status": "PASS", "quotes": quotes, "missing": response.get("missing", [])}


__all__ = ["parse_tvremix_quotes_response"]

