"""Pipeline-compatible short-interest provider (Nasdaq primary, Finnhub fallback).

Nasdaq SI provides short interest + days-to-cover via api.nasdaq.com.
When Nasdaq has no row (wrong exchange, delisted, missing data), Finnhub's
/api/v1/stock/measure?measure=short-interest-short-volume-ratio is used as a
best-effort fallback so that NYSE tickers are not systemically blind in
category ②. The authoritative hierarchy is: Nasdaq-row (DTC) > Finnhub ratio.
"""
from __future__ import annotations

from earnings_monitor.short_interest_values import build_short_interest_values

_NASDAQ_EXCHANGES = {
    "NASDAQ", "NMS", "NGS", "NGSM", "NASDAQCM", "NASDAQGM", "NASDAQGS",
}


def _is_nasdaq_listed(symbol: str) -> bool:
    if ":" not in str(symbol):
        return True
    prefix = str(symbol).split(":", 1)[0].upper().strip()
    return prefix in _NASDAQ_EXCHANGES


class ShortInterestProvider:
    def __init__(self, *, nasdaq, outstanding, finnhub_short=None):
        self.nasdaq = nasdaq
        self.outstanding = outstanding
        self.finnhub_short = finnhub_short

    def get(self, symbol: str, *, as_of: str) -> dict:
        si = None
        # Nasdaq is primary; for Nasdaq-listed symbols we always attempt it first.
        # For explicitly non-Nasdaq (NYSE:*) we still attempt Nasdaq — if it
        # returns no row we fall back to Finnhub instead of returning N/A.
        if _is_nasdaq_listed(symbol) or not _is_nasdaq_listed(symbol):
            si = self.nasdaq.get(symbol, as_of=as_of)
        outstanding = self.outstanding.get(symbol)
        shares_outstanding = (
            outstanding.get("shares_outstanding_millions")
            if isinstance(outstanding, dict) else None
        )
        nasdaq_values = build_short_interest_values(
            si, shares_outstanding_millions=shares_outstanding
        )
        # Nasdaq yielded a usable reading (has short_pct/shares) — use it.
        if nasdaq_values.get("short_pct_outstanding") is not None:
            return nasdaq_values
        # Fallback: Finnhub short interest (covers NYSE as well) if available.
        if self.finnhub_short is not None:
            try:
                fh = self.finnhub_short.get(symbol, as_of=as_of)  # type: ignore
            except Exception:
                fh = None
            if isinstance(fh, dict) and fh.get("short_pct_outstanding") is not None:
                # Merge: keep Finnhub short% but preserve dtc handling if Nasdaq had one.
                if nasdaq_values.get("days_to_cover") is not None and fh.get("days_to_cover") is None:
                    fh = dict(fh)
                    fh["days_to_cover"] = nasdaq_values.get("days_to_cover")
                fh.setdefault("exchange_unsupported", False)
                return fh
        # Nothing usable on either side — for explicitly non-Nasdaq keep the neutral N/A
        # so rules/scoring remain neutral rather than penalizing as incomplete.
        if not _is_nasdaq_listed(symbol) and nasdaq_values.get("short_pct_outstanding") is None:
            return {
                "status": "N/A",
                "exchange_unsupported": True,
                "report_date": None,
                "shares_short": None,
                "days_to_cover": None,
                "short_pct_outstanding": None,
            }
        return nasdaq_values


__all__ = ["ShortInterestProvider", "_is_nasdaq_listed"]
