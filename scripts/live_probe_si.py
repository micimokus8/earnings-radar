#!/usr/bin/env python3
"""Read-only live probe: Nasdaq short interest + Finnhub shares outstanding."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from earnings_monitor.finnhub_outstanding_client import FinnhubOutstandingClient
from earnings_monitor.nasdaq_short_interest_client import NasdaqShortInterestClient
from earnings_monitor.short_interest_provider import ShortInterestProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-path", default="Finhub Key.txt")
    parser.add_argument("--symbols", default="NASDAQ:AAPL,NASDAQ:MSFT,NASDAQ:NVDA")
    args = parser.parse_args()

    as_of = datetime.now(timezone.utc).isoformat()
    provider = ShortInterestProvider(
        nasdaq=NasdaqShortInterestClient(),
        outstanding=FinnhubOutstandingClient(key_path=args.key_path),
    )

    for symbol in [s.strip() for s in args.symbols.split(",") if s.strip()]:
        result = provider.get(symbol, as_of=as_of)
        print(f"{symbol}: status={result['status']}", end="")
        print(f" report_date={result.get('report_date')}", end="")
        pct = result.get("short_pct_outstanding")
        dtc = result.get("days_to_cover")
        print(
            f" short_pct_outstanding={pct:.4f}" if pct is not None
            else " short_pct_outstanding=None",
            end="",
        )
        print(f" days_to_cover={dtc}")


if __name__ == "__main__":
    main()

      
