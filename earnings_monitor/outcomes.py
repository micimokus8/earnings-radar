"""Session-correct earnings returns.

The entry is the price at the final check, which is near the close.
AFTER_CLOSE exits at the next session. BEFORE_OPEN exits on the report day.
Official close-to-close figures are kept beside that entry.
"""

from __future__ import annotations

from datetime import date, datetime


def _as_date(value) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _num(value):
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def _bar_map(bars) -> dict[date, dict]:
    mapped = {}
    for bar in bars or []:
        if not isinstance(bar, dict):
            continue
        day = _as_date(bar.get("date") or bar.get("datetime"))
        close = _num(bar.get("close") if "close" in bar else bar.get("c"))
        if day is None or close is None:
            continue
        open_ = _num(bar.get("open") if "open" in bar else bar.get("o"))
        mapped[day] = {"open": open_, "close": close}
    return mapped


def _pct(later, earlier):
    if later is None or earlier is None or earlier == 0:
        return None
    return (later / earlier - 1.0) * 100.0


def classify_return(ret_close) -> str:
    if ret_close is None:
        return "UNRESOLVED"
    if ret_close >= 10:
        return "PUMP"
    if ret_close >= 5:
        return "PUMP5"
    if ret_close <= -5:
        return "LOSS"
    return "FLAT"


def session_returns(*, report_type: str, report_date: str, bars, entry_price=None) -> dict:
    mapped = _bar_map(bars)
    dates = sorted(mapped)
    day = _as_date(report_date)
    if day is None or not dates:
        return {"status": "UNRESOLVED", "verdict": "UNRESOLVED"}

    later = [item for item in dates if item >= day]
    if not later or (later[0] - day).days > 3:
        return {"status": "UNRESOLVED", "verdict": "UNRESOLVED"}
    session = later[0]
    i = dates.index(session)
    kind = "AFTER_CLOSE" if str(report_type).upper() == "AFTER_CLOSE" else "BEFORE_OPEN"

    if kind == "AFTER_CLOSE":
        if i + 1 >= len(dates):
            return {"status": "PENDING", "verdict": "UNRESOLVED", "session_date": session.isoformat()}
        nxt = dates[i + 1]
        official = mapped[session]["close"]
        base = float(entry_price) if _num(entry_price) else official
        ret_open = _pct(mapped[nxt]["open"], base)
        ret_close = _pct(mapped[nxt]["close"], base)
        official_close = _pct(mapped[nxt]["close"], official)
        return _result(ret_open, ret_close, official_close, session, nxt, base)

    if i < 1:
        return {"status": "UNRESOLVED", "verdict": "UNRESOLVED", "session_date": session.isoformat()}
    prev = dates[i - 1]
    official = mapped[prev]["close"]
    base = float(entry_price) if _num(entry_price) else official
    ret_open = _pct(mapped[session]["open"], base)
    ret_close = _pct(mapped[session]["close"], base)
    official_close = _pct(mapped[session]["close"], official)
    return _result(ret_open, ret_close, official_close, session, session, base)


def _result(ret_open, ret_close, official_close, session, exit_day, base) -> dict:
    def _round(value):
        return None if value is None else round(value, 2)

    return {
        "status": "PASS",
        "verdict": classify_return(ret_close),
        "session_date": session.isoformat(),
        "exit_date": exit_day.isoformat(),
        "base_close": base,
        "ret_session_open": _round(ret_open),
        "ret_session_close": _round(ret_close),
        "ret_official_close": _round(official_close),
    }


__all__ = ["classify_return", "session_returns"]
