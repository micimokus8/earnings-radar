"""Normalize verified TVRemix technicals and OHLCV response shapes."""

from __future__ import annotations

import json


_OHLCV_FIELDS = ("t", "o", "h", "l", "c", "v")


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


def parse_tvremix_technicals_response(response) -> dict:
    payload = _unwrap_mcp(response)
    data = payload.get("data") if isinstance(payload, dict) else None
    oscillators = data.get("oscillators") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(oscillators, dict):
        return {"status": "UNKNOWN", "technicals": None, "error": "technicals_missing"}
    if not isinstance(data.get("price"), (int, float)) or not isinstance(oscillators.get("rsi"), (int, float)):
        return {"status": "UNKNOWN", "technicals": None, "error": "technical_fields_invalid"}
    return {
        "status": "PASS",
        "technicals": {
            "price": data["price"],
            "change": data.get("change"),
            "volume": data.get("volume"),
            "rsi": oscillators["rsi"],
            "recommendation": (data.get("summary") or {}).get("recommendation"),
        },
    }


def parse_tvremix_ohlcv_response(response) -> dict:
    payload = _unwrap_mcp(response)
    bars = payload.get("bars") if isinstance(payload, dict) else None
    if not isinstance(bars, list) or not bars:
        return {"status": "UNKNOWN", "bars": [], "error": "ohlcv_missing"}
    normalized = []
    for bar in bars:
        if not isinstance(bar, dict) or any(field not in bar for field in _OHLCV_FIELDS):
            return {"status": "UNKNOWN", "bars": [], "error": "ohlcv_fields_invalid"}
        if not all(isinstance(bar[field], (int, float)) for field in _OHLCV_FIELDS):
            return {"status": "UNKNOWN", "bars": [], "error": "ohlcv_types_invalid"}
        normalized.append({field: bar[field] for field in _OHLCV_FIELDS})
    return {
        "status": "PASS",
        "bars": normalized,
        "symbol": payload.get("symbol"),
        "interval": payload.get("interval"),
    }


__all__ = ["parse_tvremix_technicals_response", "parse_tvremix_ohlcv_response"]

        