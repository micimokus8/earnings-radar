from __future__ import annotations

from .rules import evaluate_core_completeness


def _category(points, max_points, unknown=None):
    unknown = unknown or []
    return {
        "points": points,
        "max_points": max_points,
        "state": "PARTIAL" if unknown else "PASS",
        "unknown": unknown,
    }


def score_candidate(values: dict) -> dict:
    completeness = evaluate_core_completeness(values)
    categories = {}

    unknown = []
    analyst_points = 0
    # No analyst coverage at all: target_upside_pct AND target_recently_cut both None
    # means the forecast returned zero analyst data. In that case, the entire category
    # gets 0 points and state="N/A" — the calendar eps_estimate alone is not an
    # analyst signal.
    no_coverage = values.get("target_upside_pct") is None and values.get("target_recently_cut") is None
    if no_coverage:
        unknown = ["target_upside_pct", "target_recently_cut", "analyst_rating"]
    else:
        if values.get("target_upside_pct") is None:
            unknown.append("target_upside_pct")
        elif values["target_upside_pct"] > 30:
            analyst_points += 1
        if values.get("eps_estimate") is None:
            unknown.append("eps_estimate")
        elif values["eps_estimate"] <= 0:
            analyst_points += 1
        if values.get("target_recently_cut") is None:
            unknown.append("target_recently_cut")
        elif values["target_recently_cut"]:
            analyst_points += 1
    if no_coverage:
        categories["analyst_expectation"] = {
            "points": 0, "max_points": 3, "state": "N/A", "unknown": unknown,
        }
    else:
        categories["analyst_expectation"] = _category(analyst_points, 3, unknown)

    if values.get("short_interest_supported") is False:
        # Exchange not covered by the Nasdaq SI source (e.g. NYSE). Neutrally
        # excluded: no points, no unknown penalty, state signals "not applicable".
        categories["short_interest"] = {
            "points": 0, "max_points": 3, "state": "N/A", "unknown": [],
        }
    else:
        unknown = []
        short_points = 0
        short_pct = values.get("short_pct_outstanding")
        days = values.get("days_to_cover")
        if short_pct is None:
            unknown.append("short_pct_outstanding")
        else:
            short_points += int(short_pct > 10) + int(short_pct > 15)
        if days is None:
            unknown.append("days_to_cover")
        else:
            short_points += int(days > 3)
        categories["short_interest"] = _category(short_points, 3, unknown)

    unknown = []
    chart_points = 0
    chart_rules = (
        ("price_1d", "ema20_1d", "below"),
        ("price_4h", "ema20_4h", "below"),
        ("ema20_1d", "ema50_1d", "below"),
    )
    for left, right, _ in chart_rules:
        if values.get(left) is None or values.get(right) is None:
            unknown.append(f"{left}/{right}")
        else:
            chart_points += int(values[left] < values[right])
    for field, threshold in (("rsi_1d", 40), ("adx_1d", 25)):
        if values.get(field) is None:
            unknown.append(field)
        else:
            chart_points += int(values[field] < threshold)
    # Cap at 2/5 when the chart is bearish on ALL timeframes (all three
    # price/EMA rules satisfied) — prevents a fully bearish chart from
    # pushing a weak score into WATCH territory.
    all_bearish = (
        values.get("price_1d") is not None
        and values.get("price_4h") is not None
        and values.get("ema20_1d") is not None
        and values.get("ema20_4h") is not None
        and values.get("ema50_1d") is not None
        and values["price_1d"] < values["ema20_1d"]
        and values["price_4h"] < values["ema20_4h"]
        and values["ema20_1d"] < values["ema50_1d"]
    )
    if all_bearish and chart_points > 2:
        chart_points = 2
    categories["chart_confirmation"] = _category(chart_points, 5, unknown)

    unknown = []
    news_points = 0
    if values.get("news_status") != "PASS":
        unknown.append("news")
    elif values.get("negative_news") is False:
        news_points += 1
    if values.get("insider_status") in {"NO_DIRECT_SELL", "NO_RECENT_FILING_FOUND"}:
        news_points += 1
    elif values.get("insider_status") in {None, "UNKNOWN", "PARTIAL"}:
        unknown.append("insider")
    if values.get("dilution_status") == "NO_DILUTION_FILING_FOUND":
        news_points += 1
    elif values.get("dilution_status") in {None, "UNKNOWN", "PARTIAL"}:
        unknown.append("dilution")
    categories["news_and_sec"] = _category(news_points, 3, unknown)

    total = sum(category["points"] for category in categories.values())
    label = None
    if completeness["final_recommendation_allowed"]:
        if total >= 10:
            label = "STRONG_SETUP"
        elif total >= 6:
            label = "WATCH"
        else:
            label = "SKIP"

    return {
        "state": completeness["state"],
        "missing": completeness["missing"],
        "final_recommendation_allowed": completeness["final_recommendation_allowed"],
        "total_points": total,
        "max_points": 14,
        "label": label,
        "categories": categories,
    }


__all__ = ["score_candidate"]
