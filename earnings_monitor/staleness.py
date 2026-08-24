from __future__ import annotations

from datetime import datetime


def assess_ohlcv_staleness(*, timeframe: str, candle_close: datetime, now: datetime, completed_sessions) -> dict:
    """Assess freshness using completed exchange sessions, not calendar hours alone."""
    if completed_sessions is None:
        return {"state": "UNKNOWN", "reason": "exchange_calendar_missing"}
    if candle_close.tzinfo is None or now.tzinfo is None:
        return {"state": "UNKNOWN", "reason": "timezone_required"}
    if candle_close > now:
        return {"state": "STALE", "reason": "candle_not_closed"}

    session_dates = sorted({str(value)[:10] for value in completed_sessions})
    candle_date = candle_close.date().isoformat()
    if candle_date not in session_dates:
        return {"state": "UNKNOWN", "reason": "candle_session_missing"}

    elapsed_sessions = sum(value > candle_date for value in session_dates)
    if timeframe == "1D":
        state = "FRESH" if elapsed_sessions <= 1 else "STALE"
    elif timeframe == "4H":
        elapsed_hours = (now - candle_close).total_seconds() / 3600
        state = "FRESH" if elapsed_hours <= 6 and elapsed_sessions <= 1 else "STALE"
    else:
        return {"state": "UNKNOWN", "reason": "unsupported_timeframe"}
    return {"state": state, "elapsed_sessions": elapsed_sessions}
