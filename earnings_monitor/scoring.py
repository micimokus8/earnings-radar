"""Pump-potential score, fixed at 8 points. Missing data scores 0.

The percent of points is not a probability. Green is allowed only when the
technical bucket beat the list average in the public replay; see bucket_stats.
"""

from __future__ import annotations

from earnings_monitor.bucket_stats import (
    GREEN_MIN_TECHNICAL_POINTS,
    WATCH_MIN_POINTS,
    note_for,
)
from earnings_monitor.rules import evaluate_core_completeness

MAX_POINTS = 8


def _spot(values: dict):
    for key in ("price", "price_1d"):
        value = values.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def _distance_to_52w(values: dict):
    spot = _spot(values)
    high = values.get("high_52w")
    if spot is not None and isinstance(high, (int, float)) and high > 0:
        return (spot / float(high) - 1.0) * 100.0
    stored = values.get("distance_to_52w_pct")
    if isinstance(stored, (int, float)):
        return float(stored)
    return None


def _room_to_resistance(values: dict):
    spot = _spot(values)
    resist = values.get("resistance_price")
    if spot is not None and isinstance(resist, (int, float)) and resist > 0:
        return (float(resist) / spot - 1.0) * 100.0
    stored = values.get("room_to_resistance_pct")
    if isinstance(stored, (int, float)):
        return float(stored)
    return None


def _exhaustion(values: dict, distance) -> str | None:
    reasons = []
    if distance is not None and distance > -3:
        reasons.append("NAHE_52W_HOCH")
    rsi = values.get("rsi_1d")
    if isinstance(rsi, (int, float)) and rsi >= 75:
        reasons.append("RSI_UEBERKAUFT")
    stoch = values.get("stoch_k_1d")
    if isinstance(stoch, (int, float)) and stoch >= 90:
        reasons.append("STOCHASTIK_OBEN")
    if values.get("news_severity") == "severe" or (
        values.get("negative_news") is True and values.get("news_severity") is None
    ):
        # Legacy callers that only set negative_news=True still block.
        # A tagged soft negative does not, it only removes news points.
        if values.get("news_severity") != "soft":
            reasons.append("NEWS_NEGATIV")
    if values.get("analyst_revision") == "down" or values.get("target_revision") == "down":
        reasons.append("ERWARTUNG_GESENKT")
    if values.get("target_recently_cut") is True and values.get("target_revision") != "up":
        reasons.append("ERWARTUNG_GESENKT")
    # de-duplicate while keeping order
    unique = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    return "+".join(unique) if unique else None


def _room_points(distance, room) -> tuple[int, list[str]]:
    unknown = []
    points = 0
    if distance is None:
        unknown.append("distance_to_52w_pct")
    elif distance <= -8:
        points += 1
    if room is None:
        unknown.append("room_to_resistance_pct")
    elif 3 <= room <= 15:
        points += 1
    return points, unknown


def _history_points(values: dict) -> tuple[int, list[str]]:
    unknown = []
    points = 0
    beat_n = values.get("beat_n") or 0
    beat = values.get("beat_rate")
    if not isinstance(beat_n, int) or beat_n < 4 or beat is None:
        unknown.append("beat_rate")
    elif beat >= 0.5:
        points += 1
    hist_n = values.get("hist_n") or 0
    hist = values.get("hist_reaction_pct")
    if not isinstance(hist_n, int) or hist_n < 4 or hist is None:
        unknown.append("hist_reaction_pct")
    elif hist > 0:
        points += 1
    return points, unknown


def _revision_points(values: dict) -> tuple[int, list[str]]:
    unknown = []
    points = 0
    analyst = values.get("analyst_revision")
    if analyst not in {"up", "down"}:
        unknown.append("analyst_revision")
    elif analyst == "up":
        points += 1
    target = values.get("target_revision")
    if target not in {"up", "down"}:
        unknown.append("target_revision")
    elif target == "up":
        points += 1
    return points, unknown


def _news_points(values: dict) -> tuple[int, list[str], bool]:
    """Positive headlines add points. Silence adds nothing.

    A soft negative headline yields no points and blocks green.
    """
    unknown = []
    if values.get("news_status") not in {"PASS", "FAIL"} and values.get("positive_news_count") is None:
        unknown.append("news")
        return 0, unknown, False
    soft = values.get("news_severity") == "soft"
    if values.get("negative_news") is True and soft:
        return 0, unknown, True
    if values.get("negative_news") is True:
        return 0, unknown, False
    count = values.get("positive_news_count")
    if not isinstance(count, int):
        unknown.append("positive_news")
        return 0, unknown, False
    points = 0
    if count >= 1:
        points += 1
    if count >= 2:
        points += 1
    return points, unknown, False


def label_for(points: int, skip_reason: str | None, *, technical_points: int, strong_blocked: bool) -> str:
    if skip_reason:
        return f"SKIP ({skip_reason})"
    green_min = GREEN_MIN_TECHNICAL_POINTS
    if (
        green_min is not None
        and technical_points >= green_min
        and not strong_blocked
        and points >= green_min
    ):
        return "STRONG_SETUP"
    if points >= WATCH_MIN_POINTS and not strong_blocked:
        return "WATCH"
    if points >= WATCH_MIN_POINTS and strong_blocked:
        return "WATCH"
    return "SKIP"


def score_candidate(values: dict) -> dict:
    completeness = evaluate_core_completeness(values)
    distance = _distance_to_52w(values)
    room = _room_to_resistance(values)
    room_points, room_unknown = _room_points(distance, room)
    history_points, history_unknown = _history_points(values)
    revision_points, revision_unknown = _revision_points(values)
    news_points, news_unknown, soft_negative = _news_points(values)

    categories = {
        "room": {
            "points": room_points,
            "max_points": 2,
            "state": "PARTIAL" if room_unknown else "PASS",
            "unknown": room_unknown,
        },
        "history": {
            "points": history_points,
            "max_points": 2,
            "state": "PARTIAL" if history_unknown else "PASS",
            "unknown": history_unknown,
        },
        "revisions": {
            "points": revision_points,
            "max_points": 2,
            "state": "PARTIAL" if revision_unknown else "PASS",
            "unknown": revision_unknown,
        },
        "news": {
            "points": news_points,
            "max_points": 2,
            "state": "PARTIAL" if news_unknown else "PASS",
            "unknown": news_unknown,
        },
    }
    total = room_points + history_points + revision_points + news_points
    technical = room_points + history_points
    skip_reason = _exhaustion(values, distance)
    # de-duplicate ERWARTUNG if both flags fired
    if skip_reason:
        parts = skip_reason.split("+")
        skip_reason = "+".join(dict.fromkeys(parts))

    label = None
    if completeness["final_recommendation_allowed"]:
        label = label_for(
            total,
            skip_reason,
            technical_points=technical,
            strong_blocked=soft_negative,
        )

    pct = round(total / MAX_POINTS * 100, 1)
    return {
        "state": completeness["state"],
        "missing": completeness["missing"],
        "final_recommendation_allowed": completeness["final_recommendation_allowed"],
        "total_points": total,
        "max_points": MAX_POINTS,
        "reachable_points": MAX_POINTS,
        "technical_points": technical,
        "score_pct": pct,
        "label": label,
        "skip_reason": skip_reason,
        "blocked": bool(skip_reason),
        "strong_blocked": soft_negative,
        "frequency_note": note_for(technical),
        "distance_to_52w_pct": None if distance is None else round(distance, 2),
        "room_to_resistance_pct": None if room is None else round(room, 2),
        "categories": categories,
    }


__all__ = ["score_candidate", "label_for", "MAX_POINTS"]
