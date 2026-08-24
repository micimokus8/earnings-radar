"""Parse Nasdaq short-interest API rows into normalized values."""

from __future__ import annotations

from datetime import date


def _parse_row(row: dict):
    settlement = str(row.get("settlementDate", ""))
    try:
        month, day, year = settlement.split("/")
        report_date = date(int(year), int(month), int(day))
    except (ValueError, TypeError):
        return None
    try:
        shares_short = int(str(row.get("interest", "")).replace(",", ""))
    except (ValueError, TypeError):
        return None
    days_to_cover = row.get("daysToCover")
    try:
        days_to_cover = float(days_to_cover)
    except (TypeError, ValueError):
        return None
    return {
        "report_date": report_date,
        "shares_short": shares_short,
        "days_to_cover": days_to_cover,
    }


def parse_nasdaq_short_interest(
    rows,
    *,
    as_of: str,
    max_age_days: int = 45,
) -> dict:
    """Return newest valid row as normalized values with staleness gate.

    FINRA short interest is published twice monthly (~9 day publication lag),
    so the default freshness window is 45 days, not 10.
    """
    parsed = [entry for entry in (_parse_row(row) for row in (rows or [])) if entry]
    if not parsed:
        return {"status": "UNKNOWN", "report_date": None,
                "shares_short": None, "days_to_cover": None}

    newest = max(parsed, key=lambda entry: entry["report_date"])
    as_of_date = date.fromisoformat(str(as_of)[:10])
    age_days = (as_of_date - newest["report_date"]).days

    result = {
        "status": "PASS",
        "report_date": newest["report_date"].isoformat(),
        "shares_short": newest["shares_short"],
        "days_to_cover": newest["days_to_cover"],
    }
    if age_days > max_age_days:
        return {"status": "STALE", "report_date": result["report_date"],
                "shares_short": None, "days_to_cover": None}
    return result


__all__ = ["parse_nasdaq_short_interest"]

      
