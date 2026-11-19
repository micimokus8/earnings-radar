"""When a pre-earnings scan is still actionable, in America/New_York.

Both sessions use two clocks, measured backwards from the cash close so
summer time, winter time and early closes land in the same kind of window:

- preselect: about two to five hours before the close (midday)
- final: 25 to 50 minutes before the close (the 30–45 minute check)

Only the final stage is a recommendation. A cron every 15 minutes from
16:00 to 20:30 UTC calls ``stage_for`` and does nothing outside those windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from earnings_monitor.exchange_calendar import (
    is_trading_day,
    next_trading_day,
    session_close,
)

_ET = ZoneInfo("America/New_York")
_OPEN = time(9, 30)
# Most before-open releases are out by 08:00. After that, "today" is no longer
# a buy-before-the-print for the morning session.
_BMO_CUTOFF = time(8, 0)


@dataclass(frozen=True)
class ScanPlan:
    report_type: str
    target_date: str
    entry_open: bool
    blocked_reason: str
    headline: str
    horizon: str


def _now(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def plan_scan(report_type: str, now: datetime | None = None) -> ScanPlan:
    kind = "AFTER_CLOSE" if str(report_type).upper() == "AFTER_CLOSE" else "BEFORE_OPEN"
    current = _now(now)
    ny = current.astimezone(_ET)
    today = ny.date()

    if kind == "AFTER_CLOSE":
        close = session_close(today)
        entry_open = close is not None and ny < close.astimezone(_ET)
        if close is None:
            reason = f"{today.isoformat()} ist kein Handelstag. Kein Kauf vor dem Schluss."
        elif not entry_open:
            reason = (
                f"Börse in New York hat am {today.isoformat()} schon geschlossen. "
                "Ein Kauf vor dem Schluss ist nicht mehr möglich."
            )
        else:
            reason = ""
        return ScanPlan(
            report_type=kind,
            target_date=today.isoformat(),
            entry_open=entry_open,
            blocked_reason=reason,
            headline=(
                f"Zahlen nach US-Schluss am {today.isoformat()}. "
                "Kauf vor 16:00 New York, solange die Börse offen ist."
            ),
            horizon=(
                "Halten bis zum nächsten Handelstag. Verkauf, wenn der Kurs dort "
                "etwa 10–20 % im Plus ist. Einstieg ist der Kurs dieser "
                "Schlusskontrolle. Gemessen wird dieser Kurs → Open und Close "
                "des Folgetags."
            ),
        )

    if is_trading_day(today) and ny.time() < _BMO_CUTOFF:
        target = today
        when = "heute früh, vor der Morgenmeldung"
    else:
        target = next_trading_day(today)
        when = "kurz vor dem Schluss des Vortags"
    return ScanPlan(
        report_type=kind,
        target_date=target.isoformat(),
        entry_open=True,
        blocked_reason="",
        headline=(
            f"Zahlen vor der Eröffnung am {target.isoformat()}. "
            f"Gedacht zum Kauf {when}."
        ),
        horizon=(
            "Halten bis zum Meldetag. Verkauf, wenn der Kurs nach der Zahl "
            "etwa 10–20 % im Plus ist. Einstieg ist der Kurs der Kontrolle "
            "vor dem Schluss des Vortags. Gemessen wird dieser Kurs → "
            "Open und Close des Meldetags."
        ),
    )


def stage_for(report_type: str, now: datetime | None = None) -> str:
    """Return preselect, final, idle or closed. The session argument is unused.

    Both lists are checked on the same New York clock: midday, then again
    shortly before that day's close.
    """
    del report_type
    current = _now(now).astimezone(_ET)
    close = session_close(current.date())
    if close is None:
        return "closed"
    minutes = (close - current).total_seconds() / 60.0
    if minutes < 0:
        return "closed"
    if 25 <= minutes <= 50:
        return "final"
    if 90 <= minutes <= 300:
        return "preselect"
    return "idle"


def cash_open_still_ahead(now: datetime | None = None) -> bool:
    current = _now(now).astimezone(_ET)
    close = session_close(current.date())
    return close is not None and current.time() < _OPEN and current < close.astimezone(_ET)


__all__ = ["ScanPlan", "plan_scan", "stage_for", "cash_open_still_ahead"]
