"""Resolve earnings tickers to TradingView's EXCHANGE:TICKER format."""
from __future__ import annotations

import json


# Explicit corrections for symbols where a bare ticker is commonly misrouted.
# Keep this small and auditable; unknown ambiguous results fail closed.
_SYMBOL_OVERRIDES = {
    "CANG": "NYSE:CANG",
}


class TvremixSymbolResolver:
    """Resolve bare tickers via TVRemix search_symbols and preserve prefixes."""

    def __init__(self, session):
        self.session = session

    @staticmethod
    def _payload(response):
        if not isinstance(response, dict):
            return {}
        result = response.get("result")
        content = result.get("content") if isinstance(result, dict) else None
        if isinstance(content, list) and content and isinstance(content[0], dict):
            text = content[0].get("text")
            try:
                return json.loads(text) if isinstance(text, str) else {}
            except json.JSONDecodeError:
                return {}
        return response

    @staticmethod
    def _matches(payload, ticker):
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        rows = data.get("symbols", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            rows = data.get("results", []) if isinstance(data, dict) else []
        ticker = ticker.upper()
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").upper()
            if symbol.endswith(":" + ticker):
                return symbol
        return None

    def resolve(self, symbol: str) -> str:
        raw = str(symbol or "").strip().upper()
        if not raw:
            return raw
        if ":" in raw:
            return raw
        if raw in _SYMBOL_OVERRIDES:
            return _SYMBOL_OVERRIDES[raw]
        result = self.session.call_tool("search_symbols", {"query": raw, "limit": 10})
        if result.get("status") == "PASS":
            resolved = self._matches(self._payload(result.get("response")), raw)
            if resolved:
                return resolved
        return raw

    def resolve_many(self, symbols):
        return [self.resolve(symbol) for symbol in symbols]


__all__ = ["TvremixSymbolResolver"]
