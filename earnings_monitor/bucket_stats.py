"""Historical frequencies for technical score buckets.

Filled from the public Nasdaq replay (large-cap earnings, 2025-11-03 to
2026-11-17, last completed close before the print). News and estimate
revisions are not in that history, so the table is keyed by technical points
(room + history only, 0 to 4).

A bucket is allowed to show green only when its average return beat the list
on both the after-close horizon and the before-open horizon, with enough
names, and without a much higher loss rate. The replay found no such bucket.
GREEN_MIN_TECHNICAL_POINTS is therefore None: nothing is painted as a
high-confidence buy.
"""

from __future__ import annotations

# List = every large-cap earnings name, not only the scored subset.
LIST_BASELINE = {
    "n": 3660,
    "next_close": {"hit": 50.5, "pump5": 12.4, "pump10": 4.6, "loss5": 10.6, "mean": 0.31},
    "report_day": {"hit": 52.0, "pump5": 13.6, "pump10": 4.0, "loss5": 11.7, "mean": 0.28},
}

# Technical points -> measured frequency. News and revisions were 0 in this
# replay, so technical points are 0, 1 or 2 for almost every name.
# Point 1 is a hair above the list average on both horizons. The next-day
# gap is 0.03 percentage points, too small to paint the name green.
# Point 2 raises the +10% tail and the loss rate; its average does not beat
# the list. Nothing is green.
BUCKETS: dict[int, dict] = {
    0: {
        "n": 418,
        "next_close": {"hit": 51.4, "pump5": 5.7, "pump10": 1.4, "loss5": 5.7, "mean": 0.15},
        "report_day": {"hit": 54.3, "pump5": 11.7, "pump10": 3.3, "loss5": 7.4, "mean": 0.53},
    },
    1: {
        "n": 1435,
        "next_close": {"hit": 51.6, "pump5": 13.7, "pump10": 5.1, "loss5": 10.5, "mean": 0.34},
        "report_day": {"hit": 53.2, "pump5": 15.1, "pump10": 4.5, "loss5": 12.1, "mean": 0.40},
    },
    2: {
        "n": 833,
        "next_close": {"hit": 49.9, "pump5": 15.0, "pump10": 5.8, "loss5": 14.9, "mean": 0.23},
        "report_day": {"hit": 51.7, "pump5": 16.2, "pump10": 5.2, "loss5": 13.1, "mean": 0.27},
    },
    3: {
        "n": 40,
        "next_close": {"hit": 45.0, "pump5": 15.0, "pump10": 7.5, "loss5": 17.5, "mean": 0.33},
        "report_day": {"hit": 52.5, "pump5": 25.0, "pump10": 12.5, "loss5": 17.5, "mean": 0.31},
    },
}

# None: no technical bucket beat the list average by a margin worth a green label.
GREEN_MIN_TECHNICAL_POINTS: int | None = None

WATCH_MIN_POINTS = 2


def note_for(technical_points: int) -> str:
    """One sentence a non-programmer can read next to 'X von Y Punkten'."""
    base_next = LIST_BASELINE["next_close"]
    base_day = LIST_BASELINE["report_day"]
    bucket = BUCKETS.get(int(technical_points))
    if not bucket:
        return (
            "Für diesen Technik-Stand liegt keine eigene Messung vor. "
            f"Die ganze Liste (n={LIST_BASELINE['n']}) machte am Folgetag "
            f"in {base_next['pump5']}% der Fälle mindestens +5 % "
            f"und in {base_next['loss5']}% mindestens −5 %."
        )
    nxt = bucket["next_close"]
    day = bucket["report_day"]
    return (
        f"Technik {int(technical_points)} von 4, n={bucket['n']}: "
        f"Folgetag mindestens +5 % in {nxt['pump5']}% (Liste {base_next['pump5']}%), "
        f"mindestens +10 % in {nxt['pump10']}% (Liste {base_next['pump10']}%), "
        f"Verlust mindestens 5 % in {nxt['loss5']}% (Liste {base_next['loss5']}%). "
        f"Meldetag vor der Eröffnung mindestens +5 % in {day['pump5']}% "
        f"(Liste {base_day['pump5']}%). Das ist die gemessene Häufigkeit, keine Chance."
    )


__all__ = [
    "LIST_BASELINE",
    "BUCKETS",
    "GREEN_MIN_TECHNICAL_POINTS",
    "WATCH_MIN_POINTS",
    "note_for",
]
