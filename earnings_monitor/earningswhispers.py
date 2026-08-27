"""EarningsWhispers discovery — primary source for curated earnings candidates.

Fetches the "Most Anticipated Earnings Releases" list from
EarningsWhispers, filtered by date and session (before-open / after-close).

API endpoint: /api/quickcaldata/{yyyymmdd}/{rt}
  rt=1 → before the open
  rt=3 → after the close

The response is a flat JSON array with one object per company, each
carrying a ``ticker`` field.

Note: The API requires an initial cookie consent. The client loads the
calendar page first to establish a session, then calls the API with the
same cookie jar.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import http.cookiejar
from datetime import date as Date

_BASE_URL = "https://www.earningswhispers.com"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{_BASE_URL}/calendar",
}
_PAGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "text/html",
}

# Mapping from report type to EW session code
_SESSION = {"BEFORE_OPEN": 1, "AFTER_CLOSE": 3}


class EarningsWhispersClient:
    """Fetch the "Most Anticipated" earnings list for a given date + session."""

    def __init__(self, *, timeout: float = 15.0):
        self.timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self._session_initialized = False

    def _ensure_session(self) -> None:
        """Load the calendar page once to establish cookies (consent)."""
        if self._session_initialized:
            return
        try:
            req = urllib.request.Request(
                f"{_BASE_URL}/calendar",
                headers=dict(_PAGE_HEADERS),
            )
            self._opener.open(req, timeout=self.timeout)
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, OSError):
            pass  # Non-fatal — the API call is the real test
        self._session_initialized = True

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
        self._ensure_session()
        rt = _SESSION.get(report_type.upper(), 1)
        yyyymmdd = target_date.strftime("%Y%m%d")

        url = f"{_BASE_URL}/api/quickcaldata/{yyyymmdd}/{rt}"
        try:
            req = urllib.request.Request(url, headers=dict(_HEADERS))
            with self._opener.open(req, timeout=self.timeout) as resp:
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