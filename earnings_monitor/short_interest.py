"""Deterministic short-interest normalization and freshness checks."""

from __future__ import annotations

from datetime import date


def _unknown(reason: str):
    return {
        "status": "UNKNOWN",
        "short_pct_float": None,
        "days_to_cover": None,
        "reason": reason,
    }


def normalize_short_interest(raw: dict, *, as_of: str, max_age_days: int = 10) -> dict:
    if not isinstance(raw, dict):
        return _unknown("invalid_response")
    try:
        float_millions = float(raw["floatingShare"])
        short_quantity = float(raw["shortQty"])
        days_to_cover = float(raw["daysToCover"])
        report_date = date.fromisoformat(str(raw["reportDate"])[:10])
        observed_date = date.fromisoformat(str(as_of)[:10])
    except (KeyError, TypeError, ValueError):
        return _unknown("required_field_missing_or_invalid")

    age_days = (observed_date - report_date).days
    if age_days < 0:
        return _unknown("report_date_in_future")
    if age_days > max_age_days:
        return {
            "status": "STALE",
            "short_pct_float": None,
            "days_to_cover": None,
            "reason": "report_too_old",
            "age_days": age_days,
        }
    if float_millions <= 0 or short_quantity < 0 or days_to_cover < 0:
        return _unknown("implausible_value")

    float_shares = float_millions * 1_000_000
    short_pct_float = short_quantity / float_shares * 100
    if short_pct_float < 0 or short_pct_float > 100:
        return _unknown("short_percent_out_of_range")
    return {
        "status": "PASS",
        "short_pct_float": short_pct_float,
        "days_to_cover": days_to_cover,
        "report_date": report_date.isoformat(),
        "age_days": age_days,
    }


__all__ = ["normalize_short_interest"]

        
  