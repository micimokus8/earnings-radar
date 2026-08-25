from __future__ import annotations


_CORE_FIELDS = ("price", "eps_estimate", "ohlcv_1d", "market_cap", "short_pct_outstanding", "days_to_cover")


def evaluate_news_sec(*, news_status, negative_news, insider_status, dilution_status):
    unknown = []
    points = 0
    if news_status == "PASS":
        points += int(not negative_news)
    else:
        unknown.append("news")
    if insider_status == "NO_DIRECT_SELL":
        points += 1
    elif insider_status in {"UNKNOWN", "PARTIAL"}:
        unknown.append("insider")
    if dilution_status == "NO_DILUTION_FILING_FOUND":
        points += 1
    elif dilution_status in {"UNKNOWN", "PARTIAL"}:
        unknown.append("dilution")
    state = "PARTIAL" if unknown else "PASS"
    return {"state": state, "points": points, "unknown": unknown}


def evaluate_core_completeness(values):
    missing = [name for name in _CORE_FIELDS if values.get(name) is None]
    # Short-interest is only available for Nasdaq-listed symbols. When it is
    # structurally unsupported (e.g. NYSE), treat its core fields as satisfied so
    # the candidate is not unfairly disqualified as INCOMPLETE.
    if values.get("short_interest_supported") is False:
        missing = [name for name in missing
                   if name not in ("short_pct_outstanding", "days_to_cover")]
    return {
        "state": "INCOMPLETE" if missing else "COMPLETE",
        "missing": missing,
        "final_recommendation_allowed": not missing,
    }


def _reset_for_testing():
    return None


__all__ = ["evaluate_news_sec", "evaluate_core_completeness"]
