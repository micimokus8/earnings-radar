"""Pipeline-compatible short-interest provider (Nasdaq + Finnhub)."""

from __future__ import annotations

from earnings_monitor.short_interest_values import build_short_interest_values

# The Nasdaq short-interest endpoint only covers Nasdaq-listed securities.
# Explicitly non-Nasdaq exchanges cannot provide this data by design, so we
# return an "N/A" (exchange not covered) result instead of a hard failure that
# would otherwise disqualify the candidate as INCOMPLETE.
_NASDAQ_EXCHANGES = {
    "NASDAQ", "NMS", "NGS", "NGSM", "NASDAQCM", "NASDAQGM", "NASDAQGS",
}


def _is_nasdaq_listed(symbol: str) -> bool:
    if ":" not in str(symbol):
        # No exchange prefix: attempt the Nasdaq lookup as a best effort
        # (manual/bare tickers). Only treat an *explicit* non-Nasdaq prefix as
        # structurally unsupported.
        return True
    prefix = str(symbol).split(":", 1)[0].upper().strip()
    return prefix in _NASDAQ_EXCHANGES


class ShortInterestProvider:
    def __init__(self, *, nasdaq, outstanding):
        self.nasdaq = nasdaq
        self.outstanding = outstanding

    def get(self, symbol: str, *, as_of: str) -> dict:
        if not _is_nasdaq_listed(symbol):
            return {
                "status": "N/A",
                "exchange_unsupported": True,
                "report_date": None,
                "shares_short": None,
                "days_to_cover": None,
                "short_pct_outstanding": None,
            }
        si = self.nasdaq.get(symbol, as_of=as_of)
        outstanding = self.outstanding.get(symbol)
        shares_outstanding = (
            outstanding.get("shares_outstanding_millions")
            if isinstance(outstanding, dict) else None
        )
        return build_short_interest_values(
            si, shares_outstanding_millions=shares_outstanding
        )


__all__ = ["ShortInterestProvider", "_is_nasdaq_listed"]
