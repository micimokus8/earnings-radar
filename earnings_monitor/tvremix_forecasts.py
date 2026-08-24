"""Normalize TVRemix forecast responses without network access."""

from __future__ import annotations

import json

from earnings_monitor.forecasts import normalize_forecast


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


def parse_tvremix_forecast_response(response, price=1.0) -> dict:
    if not isinstance(response, dict):
        return {"status": "UNKNOWN", "forecast": None, "error": "invalid_response"}

    response = _unwrap_mcp(response)
    if not isinstance(response, dict):
        return {"status": "UNKNOWN", "forecast": None, "error": "invalid_response"}
    raw = response.get("data")
    if raw is None:
        results = response.get("results")
        if isinstance(results, list) and len(results) == 1:
            raw = results[0]
    if not isinstance(raw, dict):
        return {"status": "UNKNOWN", "forecast": None, "error": "forecast_missing"}

    raw = dict(raw)
    rating = raw.get("analyst_rating")
    if isinstance(rating, dict):
        raw["analyst_rating"] = rating.get("recommendation")
    normalized = normalize_forecast(raw, price=price)
    return {"status": normalized["status"], "forecast": normalized}


__all__ = ["parse_tvremix_forecast_response"]
