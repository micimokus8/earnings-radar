from __future__ import annotations


def detect_target_cut(*, previous_average, current_average, minimum_change_pct: float = 2.0) -> dict:
    if previous_average is None or current_average is None or previous_average <= 0:
        return {"status": "UNKNOWN", "cut": None, "change_pct": None}
    change_pct = (current_average - previous_average) / previous_average * 100
    cut = change_pct <= -abs(minimum_change_pct)
    return {"status": "PASS", "cut": cut, "change_pct": round(change_pct, 4)}


__all__ = ["detect_target_cut"]
