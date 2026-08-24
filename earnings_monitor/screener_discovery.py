"""Discover earnings symbols from TV screener rows (date-sorted, client-filtered)."""

from __future__ import annotations


def parse_screener_rows(rows, *, target_date: str) -> list[str]:
    """Return deduplicated symbols with earnings exactly on target_date.

    Rows are expected from run_screener sorted ascending by
    earnings_release_next_date; filtering happens client-side so no
    server filter syntax is required.
    """
    matched = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("earnings_release_next_date") != target_date:
            continue
        symbol = row.get("symbol")
        if not symbol:
            continue
        matched.append((symbol, row.get("market_cap_basic") or 0))

    seen = set()
    unique = []
    for symbol, _mcap in matched:
        if symbol in seen:
            continue
        seen.add(symbol)
        unique.append((symbol, next(
            m for s, m in matched if s == symbol)))
    unique.sort(key=lambda item: item[1], reverse=True)
    return [symbol for symbol, _mcap in unique]


__all__ = ["parse_screener_rows"]

      
