"""Beat rate and past earnings reaction from public prints and daily bars.

Unknown announcement time is skipped. Mixing a before-open gap with an
after-close overnight move would invent a reaction the trade does not have.
"""

from __future__ import annotations

from datetime import date, datetime


_BMO = {"bmo", "before market open", "before-open", "time-pre-market", "1"}
_AMC = {"amc", "after market close", "after-close", "time-after-hours", "3"}


def _as_date(value) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _num(value):
    if isinstance(value, (int, float)):
        return float(value)
    return None


def summarize_earnings_history(events, bars, *, as_of: str) -> dict:
    """Summarise prints strictly before *as_of*.

    ``events`` items: date, hour (bmo/amc), eps_actual, eps_estimate.
    ``bars`` items: date, open, high, low, close. Completed sessions only.
    """
    empty = {
        "beat_rate": None,
        "beat_n": 0,
        "hist_reaction_pct": None,
        "hist_n": 0,
    }
    cutoff = _as_date(as_of)
    if cutoff is None:
        return empty

    by_date = {}
    for bar in bars or []:
        if not isinstance(bar, dict):
            continue
        day = _as_date(bar.get("date") or bar.get("datetime"))
        close = _num(bar.get("close") if "close" in bar else bar.get("c"))
        if day is None or close is None or close <= 0:
            continue
        by_date[day] = {"close": close}
    dates = sorted(by_date)
    index = {day: i for i, day in enumerate(dates)}

    beats = []
    reactions = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        day = _as_date(event.get("date") or event.get("earnings_date"))
        if day is None or day >= cutoff:
            continue
        actual = _num(event.get("eps_actual") if "eps_actual" in event else event.get("epsActual"))
        estimate = _num(event.get("eps_estimate") if "eps_estimate" in event else event.get("epsEstimate"))
        if actual is not None and estimate is not None:
            beats.append(actual > estimate)
        hour = str(event.get("hour") or event.get("timing") or "").strip().lower()
        if day not in index:
            continue
        i = index[day]
        if hour in _BMO and i >= 1:
            prev = by_date[dates[i - 1]]["close"]
            reactions.append((by_date[day]["close"] / prev - 1.0) * 100.0)
        elif hour in _AMC and i + 1 < len(dates):
            nxt = by_date[dates[i + 1]]["close"]
            reactions.append((nxt / by_date[day]["close"] - 1.0) * 100.0)

    beat_rate = round(sum(beats) / len(beats), 4) if len(beats) >= 4 else None
    hist = round(sum(reactions) / len(reactions), 2) if len(reactions) >= 4 else None
    return {
        "beat_rate": beat_rate,
        "beat_n": len(beats),
        "hist_reaction_pct": hist,
        "hist_n": len(reactions),
    }


__all__ = ["summarize_earnings_history"]
