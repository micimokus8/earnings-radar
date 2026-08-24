#!/usr/bin/env python3
"""Diagnostic: market-wide calendar call variants + discovery result."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from earnings_monitor.discovery import discover_earnings_symbols
from earnings_monitor.wiring import build_tvremix_session
from earnings_monitor.tvremix_calendar_client import TvremixCalendarClient


def main() -> None:
    import argparse
    from datetime import timedelta

    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=0)
    args = parser.parse_args()

    target = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    end_date = (
        datetime.now(ZoneInfo("America/New_York")) + timedelta(days=args.days)
    ).strftime("%Y-%m-%d")
    print("ny_today:", target, "window_end:", end_date)
    session = build_tvremix_session(secret_path="tvremix API.txt")
    client = TvremixCalendarClient(session)

    block = client.get(symbols=None, date_from=target, date_to=end_date)
    events = block.get("events", [])
    print(f"status={block.get('status')} events={len(events)} "
          f"error={block.get('error')}")
    found = discover_earnings_symbols(
        [e for e in events], target_date=target
    )
    print("discovered_today:", len(found), found[:8])
    dates = sorted({e.get("earnings_date") for e in events if e.get("earnings_date")})
    print("dates_in_window:", dates[:10])


if __name__ == "__main__":
    main()

      
