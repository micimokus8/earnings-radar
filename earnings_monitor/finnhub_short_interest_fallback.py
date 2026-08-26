"""Finnhub short-interest fallback (NYSE coverage) + helpers.

Best-effort fallback for NYSE tickers: Finnhub /api/v1/stock/measure?measure=
short-interest-short-volume-ratio?symbol={TICKER} (share outstanding already
via FinnhubOutstandingClient). Finnhub returns a short-interest ratio (short
volume / outstanding) which we treat as a conservative proxy. Never blocks
a candidate: status-aware, reuses the same X-Finnhub-Token, and degrades to
short_pct_outstanding=None on any parse/HTTP failure.
"""

from __future__ import annotations

import json
import urllib.request


def _ticker(symbol: str) -> str:
    return str(symbol).split(":", 1)[-1].strip().upper()


class FinnhubShortInterestFallback:
    def __init__(self, *, key_path: str, requester=None, timeout: float = 20.0):
        self.key_path = key_path
        self.timeout = timeout
        self.requester = requester  # injected in tests

    def _token(self) -> str | None:
        try:
            text = open(self.key_path, encoding="utf-8").read().strip()
        except OSError:
            return None
        return text or None

    def _request(self, symbol: str) -> dict | None:
        token = self._token()
        if not token:
            return None
        ticker = _ticker(symbol)
        url = (
            "https://finnhub.io/api/v1/stock/measure"
            f"?symbol={ticker}&measure=short-interest-short-volume-ratio"
        )
        if self.requester is not None:
            resp = self.requester(url, headers={"X-Finnhub-Token": token}, timeout=self.timeout)
            status = int(resp.get("status", 0) or 0)
            body = resp.get("body", b"")
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            payload = json.loads(body) if body.strip() else []
            return {"status": status, "payload": payload}
        req = urllib.request.Request(url, headers={"X-Finnhub-Token": token})
        import urllib.error as _err
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = r.read().decode("utf-8")
                return {"status": int(r.status), "payload": json.loads(body) if body.strip() else []}
        except _err.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
                payload = json.loads(body) if body.strip() else []
                return {"status": int(exc.code), "payload": payload}
            except Exception:
                return {"status": int(exc.code), "payload": []}
        except Exception:
            return None

    def get(self, symbol: str, *, as_of: str | None = None) -> dict | None:
        wrapper = self._request(symbol)
        if wrapper is None or int(wrapper.get("status", 0)) != 200:
            return None
        rows = wrapper.get("payload") or []
        if not isinstance(rows, list):
            rows = [rows]
        # Array of {symbol, period, shareOutstanding...} like outstanding.
        # For short-interest ratio Finnhub returns: {date, value} (ratio as .)
        # Find latest row with a numeric value.
        best = None
        for row in reversed(sorted(rows, key=lambda r: (r.get("date") or r.get("period") or ""))):
            if not isinstance(row, dict):
                continue
            for key in ("value", "ratio", "shortInterest", "short_volume_ratio", "shortVolumeRatio"):
                raw = row.get(key)
                if raw is None:
                    continue
                try:
                    v = float(raw)
                    if 0 < v < 1.0:
                        # Finnhub ratio 0.0..1.0 -> percent
                        return {
                            "status": "PASS",
                            "report_date": row.get("date") or row.get("period"),
                            "shares_short": None,
                            "days_to_cover": None,
                            "short_pct_outstanding": v * 100.0,
                        }
                except Exception:
                    continue
            if best is None:
                best = row
        # No ratio row found — check outstanding-style rows with shares.
        return None


__all__ = ["FinnhubShortInterestFallback"]
