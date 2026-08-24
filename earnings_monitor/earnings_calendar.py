from __future__ import annotations

from .nasdaq_timing import classify_nasdaq_timing


def normalize_earnings_calendar(raw_events, *, timing_by_symbol):
    if raw_events is None:
        return []
    normalized = []
    for event in raw_events:
        symbol = event.get("symbol")
        missing = []
        if not symbol:
            missing.append("symbol")
        timing = classify_nasdaq_timing(timing_by_symbol.get(symbol))["state"]
        if not event.get("next_earnings_date"):
            missing.append("next_earnings_date")
        if missing:
            status = "INCOMPLETE"
        elif timing == "UNKNOWN":
            status = "PARTIAL"
        else:
            status = "PASS"
        normalized.append({
            "symbol": symbol,
            "earnings_date": event.get("next_earnings_date"),
            "earnings_timing": timing,
            "eps_estimate": event.get("eps_estimate"),
            "revenue_estimate": event.get("revenue_estimate"),
            "status": status,
            "missing": missing,
        })
    return normalized


__all__ = ["normalize_earnings_calendar"]
