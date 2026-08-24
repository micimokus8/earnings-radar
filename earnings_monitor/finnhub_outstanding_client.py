"""Finnhub client for shares outstanding (short-% denominator)."""

from __future__ import annotations

import json
import urllib.request

_URL = "https://finnhub.io/api/v1/stock/profile2"


def _default_requester(url: str, *, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return {"status": response.status, "body": response.read()}


def _ticker(symbol: str) -> str:
    return str(symbol).split(":")[-1].strip().upper()


class FinnhubOutstandingClient:
    def __init__(self, *, key_path: str, requester=_default_requester,
                 timeout: float = 20.0):
        self.key_path = key_path
        self.requester = requester
        self.timeout = timeout

    def _token(self):
        with open(self.key_path, encoding="utf-8") as handle:
            return handle.read().strip()

    def get(self, symbol: str) -> dict:
        unknown = {"status": "UNKNOWN", "shares_outstanding_millions": None,
                   "report_date": None}
        try:
            token = self._token()
            if not token:
                return unknown
            url = f"{_URL}?symbol={_ticker(symbol)}"
            response = self.requester(
                url, headers={"X-Finnhub-Token": token}, timeout=self.timeout
            )
            if int(response.get("status", 0)) != 200:
                return {**unknown, "error": f"HTTP {response.get('status')}"}
            payload = json.loads(response["body"].decode("utf-8"))
            outstanding = payload.get("shareOutstanding")
            value = float(outstanding)
            if value <= 0:
                return unknown
            return {"status": "PASS", "shares_outstanding_millions": value,
                    "report_date": None}
        except Exception as exc:
            return {**unknown, "error": type(exc).__name__}


__all__ = ["FinnhubOutstandingClient"]

      
