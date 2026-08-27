"""EarningsWhispers discovery — primary source for curated earnings candidates.

Fetches the "Most Anticipated Earnings Releases" list from
EarningsWhispers, filtered by date and session (before-open / after-close).

API endpoint: /api/quickcaldata/{yyyymmdd}/{rt}
  rt=1 → before the open
  rt=3 → after the close

The response is a flat JSON array with one object per company, each
carrying a ``ticker`` field.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date as Date
from datetime import timedelta as TD

_BASE_URL = "https://www.earningswhispers.com"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}

# Mapping from report type to EW session code
_SESSION = {"BEFORE_OPEN": 1, "AFTER_CLOSE": 3}


def _yyyymmdd(d: Date) -> str:
    return d.strftime("%Y%m%d")


def _ew_date(d: Date) -> str:
    """Convert a Python date to the yyyymmdd format used by EW's API."""
    return _yyyymmdd(d)


class EarningsWhispersClient:
    """Fetch the "Most Anticipated" earnings list for a given date + session."""

    def __init__(self, *, timeout: float = 15.0):
        self.timeout = timeout

    def get_symbols(
        self,
        target_date: Date | None = None,
        report_type: str = "BEFORE_OPEN",
    ) -> list[str] | None:
        """Return the list of tickers for *target_date* and *report_type*.

        Returns None on any network or parse error (caller should fall back).
        """
        if target_date is None:
            target_date = Date.today()
        rt = _SESSION.get(report_type.upper(), 1)
        yyyymmdd = _ew_date(target_date)

        url = f"{_BASE_URL}/api/quickcaldata/{yyyymmdd}/{rt}"
        try:
            request = urllib.request.Request(url, headers=dict(_HEADERS))
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                if resp.status != 200:
                    return None
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, (list, tuple)):
            return None

        symbols = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            ticker = entry.get("ticker") or entry.get("symbol")
            if isinstance(ticker, str) and ticker.strip():
                symbols.append(ticker.strip().upper())
        return symbols if symbols else None


__all__ = ["EarningsWhispersClient"]