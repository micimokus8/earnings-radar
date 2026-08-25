"""Discover earnings symbols from TV screener rows (date-sorted, client-filtered)."""

from __future__ import annotations

from earnings_monitor.dedup import dedupe_dual_class_symbols


def parse_screener_rows(rows, *, target_date: str) -> list[str]:
    """Return deduplicated symbols with earnings exactly on target_date.

    Rows are expected from run_screener sorted ascending by
    earnings_release_next_date; we keep deduplicated server order so a
    symbol cap is NOT biased toward market cap. Size filtering (if any) is
    applied separately in the client via min_market_cap. Dual-class share
    tickers (e.g. HEI / HEI.A) are collapsed to a single symbol per company.
    """
    seen = set()
    ordered = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("earnings_release_next_date") != target_date:
            continue
        symbol = row.get("symbol")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        ordered.append(symbol)
    return dedupe_dual_class_symbols(ordered)


__all__ = ["parse_screener_rows"]

      
