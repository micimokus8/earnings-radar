"""HTTP client for the verified Nasdaq short-interest endpoint."""

from __future__ import annotations

import json
import urllib.request

from earnings_monitor.nasdaq_short_interest import parse_nasdaq_short_interest

_BASE_URL = "https://api.nasdaq.com/api/quote/{ticker}/short-interest"
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def _default_requester(url: str, *, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return {"status": response.status, "body": response.read()}


def _ticker(symbol: str) -> str:
    return str(symbol).split(":")[-1].strip().upper()


class NasdaqShortInterestClient:
    def __init__(self, *, requester=_default_requester, timeout: float = 20.0):
        self.requester = requester
        self.timeout = timeout

    def get(self, symbol: str, *, as_of: str) -> dict:
        unknown = {"status": "UNKNOWN", "report_date": None,
                   "shares_short": None, "days_to_cover": None}
        url = _BASE_URL.format(ticker=_ticker(symbol)) + "?assetclass=stocks&limit=6"
        try:
            response = self.requester(url, headers=dict(_DEFAULT_HEADERS),
                                      timeout=self.timeout)
            if int(response.get("status", 0)) != 200:
                return {**unknown, "error": f"HTTP {response.get('status')}"}
            payload = json.loads(response["body"].decode("utf-8"))
            rows = payload["data"]["shortInterestTable"]["rows"]
            return parse_nasdaq_short_interest(rows, as_of=as_of)
        except Exception as exc:
            return {**unknown, "error": type(exc).__name__}


__all__ = ["NasdaqShortInterestClient"]

      
