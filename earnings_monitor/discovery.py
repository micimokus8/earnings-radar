"""Pick today's earnings symbols from a market-wide calendar response."""

from __future__ import annotations


def discover_earnings_symbols(events, *, target_date: str) -> list[str]:
    """Return deduplicated symbols reporting exactly on target_date."""
    seen = set()
    ordered = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        symbol = event.get("symbol")
        if not symbol or symbol in seen:
            continue
        if event.get("earnings_date") != target_date:
            continue
        seen.add(symbol)
        ordered.append(symbol)
    return ordered


__all__ = ["discover_earnings_symbols"]

      
