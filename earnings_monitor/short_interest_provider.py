"""Pipeline-compatible short-interest provider (Nasdaq + Finnhub)."""

from __future__ import annotations

from earnings_monitor.short_interest_values import build_short_interest_values


class ShortInterestProvider:
    def __init__(self, *, nasdaq, outstanding):
        self.nasdaq = nasdaq
        self.outstanding = outstanding

    def get(self, symbol: str, *, as_of: str) -> dict:
        si = self.nasdaq.get(symbol, as_of=as_of)
        outstanding = self.outstanding.get(symbol)
        shares_outstanding = (
            outstanding.get("shares_outstanding_millions")
            if isinstance(outstanding, dict) else None
        )
        return build_short_interest_values(
            si, shares_outstanding_millions=shares_outstanding
        )


__all__ = ["ShortInterestProvider"]

      
