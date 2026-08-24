from __future__ import annotations

from datetime import date


def classify_dilution_filings(filings, *, as_of: str) -> dict:
    if filings is None:
        return {"status": "UNKNOWN", "point_deduction": False, "evidence": []}

    cutoff_424b5 = date.fromisoformat(as_of).toordinal() - 30
    cutoff_shelf = date.fromisoformat(as_of).toordinal() - 90
    recent_shelf = []
    recent_424b5 = []

    for filing in filings:
        try:
            filed = date.fromisoformat(filing["filed"]).toordinal()
        except (KeyError, TypeError, ValueError):
            continue
        form = str(filing.get("form", "")).upper()
        if form == "424B5" and filed >= cutoff_424b5:
            recent_424b5.append(filing)
        elif form == "S-3" and filed >= cutoff_shelf:
            recent_shelf.append(filing)
        elif form == "S-1" and filed >= cutoff_shelf:
            recent_shelf.append(filing)

    if recent_424b5:
        return {"status": "CONFIRMED_DILUTION", "point_deduction": True, "evidence": recent_424b5}
    if recent_shelf:
        status = "SHELF_ACTIVE" if any(str(x.get("form", "")).upper() == "S-3" for x in recent_shelf) else "SHELF_FILED"
        return {"status": status, "point_deduction": False, "evidence": recent_shelf}
    return {"status": "NO_DILUTION_FILING_FOUND", "point_deduction": False, "evidence": []}
