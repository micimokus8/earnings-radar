"""Combine Nasdaq short-interest rows with shares outstanding."""

from __future__ import annotations


def build_short_interest_values(si: dict, *, shares_outstanding_millions) -> dict:
    """Merge parsed SI row and outstanding-share count into score values.

    The percentage denominator is documented as *shares outstanding*
    (not free float); days_to_cover is the primary short signal.
    """
    status = si.get("status", "UNKNOWN")
    report_date = si.get("report_date")
    base = {
        "status": status,
        "report_date": report_date,
        "short_pct_outstanding": None,
        "days_to_cover": si.get("days_to_cover"),
    }
    if status != "PASS":
        return base
    if si.get("shares_short") is None:
        return {**base, "status": "UNKNOWN"}

    try:
        denominator = float(shares_outstanding_millions) * 1_000_000.0
    except (TypeError, ValueError):
        return {**base, "status": "PARTIAL"}
    if denominator <= 0:
        return {**base, "status": "PARTIAL"}

    pct = si["shares_short"] / denominator * 100.0
    if not 0.0 <= pct <= 100.0:
        return {**base, "status": "PARTIAL"}

    return {
        **base,
        "short_pct_outstanding": pct,
    }


__all__ = ["build_short_interest_values"]

      
