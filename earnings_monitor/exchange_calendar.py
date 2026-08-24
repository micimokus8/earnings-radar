"""NYSE trading calendar: holidays, early closes, sessions (stdlib only)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
_REGULAR_CLOSE = time(16, 0)
_EARLY_CLOSE = time(13, 0)


def _easter(year: int) -> date:
    """Gregorian computus (Meeus/Jones/Butcher)."""
    y = year
    a = y % 19
    b, c = divmod(y, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def _roll_observed(day: date) -> date:
    if day.weekday() == 5:   # Saturday -> preceding Friday
        return day - timedelta(days=1)
    if day.weekday() == 6:   # Sunday -> following Monday
        return day + timedelta(days=1)
    return day


def nyse_holidays(year: int) -> set[date]:
    easter_sunday = _easter(year)
    fixed = [date(year, 1, 1), date(year, 6, 19),
             date(year, 7, 4), date(year, 12, 25)]
    holidays = {_roll_observed(day) for day in fixed}
    holidays |= {
        _nth_weekday(year, 1, 0, 3),                       # MLK
        _nth_weekday(year, 2, 0, 3),                       # Presidents
        easter_sunday - timedelta(days=2),                 # Good Friday
        _last_weekday(year, 5, 0),                         # Memorial
        _nth_weekday(year, 9, 0, 1),                       # Labor
        _nth_weekday(year, 11, 3, 4),                      # Thanksgiving
    }
    return holidays


def early_close_dates(year: int) -> set[date]:
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    candidates = {thanksgiving + timedelta(days=1), date(year, 12, 24)}
    holidays = nyse_holidays(year)
    return {day for day in candidates if day not in holidays}


def trading_sessions(start_date: date, end_date: date) -> list[date]:
    holidays = set()
    for year in {start_date.year, end_date.year}:
        holidays |= nyse_holidays(year)
    sessions = []
    day = start_date
    while day <= end_date:
        if day.weekday() < 5 and day not in holidays:
            sessions.append(day)
        day += timedelta(days=1)
    return sessions


def completed_sessions_before(now_utc: datetime, *, lookback_days: int = 10) -> list[date]:
    now_utc = now_utc.astimezone(timezone.utc)
    start = (now_utc + timedelta(days=1)).date() - timedelta(days=lookback_days)
    end = (now_utc + timedelta(days=1)).date()
    early_closes = set()
    for year in {start.year, end.year}:
        early_closes |= early_close_dates(year)
    completed = []
    for session in trading_sessions(start, end):
        close_time = _EARLY_CLOSE if session in early_closes else _REGULAR_CLOSE
        closing = datetime.combine(session, close_time, tzinfo=_ET)
        if closing.astimezone(timezone.utc) <= now_utc:
            completed.append(session)
    return completed


__all__ = [
    "nyse_holidays",
    "early_close_dates",
    "trading_sessions",
    "completed_sessions_before",
]

      
