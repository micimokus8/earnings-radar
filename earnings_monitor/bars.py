"""Drop candles that have not finished yet."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from earnings_monitor.exchange_calendar import session_close


def _bar_day(bar: dict) -> date | None:
    raw = bar.get("datetime") or bar.get("date") or bar.get("t")
    if raw is None:
        return None
    text = str(raw).replace(" ", "T")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _bar_dt(bar: dict) -> datetime | None:
    raw = bar.get("datetime") or bar.get("date") or bar.get("t")
    if raw is None:
        return None
    text = str(raw).strip().replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def drop_unfinished_daily(bars: list[dict], now: datetime | None = None) -> list[dict]:
    """Remove a daily bar whose cash session has not closed.

    Bars without a timestamp are kept (older fixtures). A bar is unfinished
    when *now* is still before that session's New York close.
    """
    if not bars:
        return []
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    kept = list(bars)
    while kept:
        day = _bar_day(kept[-1])
        if day is None:
            break
        close = session_close(day)
        if close is not None and now < close.astimezone(timezone.utc):
            kept.pop()
            continue
        break
    return kept


def drop_unfinished_intraday(bars: list[dict], *, hours: int = 4, now: datetime | None = None) -> list[dict]:
    """Drop the last intraday bar if its window is still open."""
    if not bars:
        return []
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    started = _bar_dt(bars[-1])
    if started is None:
        return list(bars)
    if now < started.astimezone(timezone.utc) + timedelta(hours=hours):
        return list(bars[:-1])
    return list(bars)


__all__ = ["drop_unfinished_daily", "drop_unfinished_intraday"]
