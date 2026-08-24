from __future__ import annotations


def classify_nasdaq_timing(raw_value: str | None) -> dict:
    mapping = {
        "time-pre-market": "BEFORE_OPEN",
        "time-after-hours": "AFTER_CLOSE",
    }
    state = mapping.get(raw_value, "UNKNOWN")
    return {
        "state": state,
        "source_value": raw_value,
        "known": state != "UNKNOWN",
    }
