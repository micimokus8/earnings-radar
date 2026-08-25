"""Deterministic orchestration of normalized earnings data sources."""

from __future__ import annotations

import time

from earnings_monitor.candidate import build_candidate
from earnings_monitor.dedup import dedupe_dual_class_symbols


class EarningsPipeline:
    """Run the source clients and build one candidate per calendar event."""

    def __init__(
        self,
        *,
        calendar,
        quotes,
        forecasts,
        technicals,
        news,
        short_interest,
        insider=None,
        dilution=None,
        retries: int = 2,
        backoff_seconds: float = 0.75,
        sleep=time.sleep,
        throttle_seconds: float = 0.0,
    ):
        self.calendar = calendar
        self.quotes = quotes
        self.forecasts = forecasts
        self.technicals = technicals
        self.news = news
        self.short_interest = short_interest
        self.insider = insider
        self.dilution = dilution
        self.retries = max(0, int(retries))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self._sleep = sleep
        self.throttle_seconds = max(0.0, float(throttle_seconds))

    @staticmethod
    def _unknown(error: Exception | str) -> dict:
        return {"status": "UNKNOWN", "error": str(error)}

    def _call(self, client, *args, **kwargs):
        last_value = None
        if self.throttle_seconds:
            self._sleep(self.throttle_seconds)
        for attempt in range(self.retries + 1):
            try:
                value = (
                    client(*args, **kwargs)
                    if callable(client) else client.get(*args, **kwargs)
                )
            except Exception as exc:  # transient transport errors are retried
                last_value = self._unknown(exc)
            else:
                if isinstance(value, str):
                    return value
                if isinstance(value, dict):
                    if value.get("status") == "UNKNOWN" and attempt < self.retries:
                        last_value = value
                    else:
                        return value
                else:
                    return self._unknown("invalid_source_result")
            if attempt < self.retries and self.backoff_seconds:
                self._sleep(self.backoff_seconds * (2 ** attempt))
        return last_value if last_value is not None else self._unknown("exhausted")

    def run(self, symbols, *, as_of: str, date_from=None, date_to=None) -> dict:
        requested_raw = list(dict.fromkeys(symbols))
        requested = dedupe_dual_class_symbols(requested_raw)
        removed_duplicate_symbols = [s for s in requested_raw if s not in set(requested)]
        calendar = self._call(
            self.calendar,
            symbols=requested,
            date_from=date_from,
            date_to=date_to,
        )
        quotes = self._call(self.quotes, requested)
        events = calendar.get("events", []) if isinstance(calendar, dict) else []
        event_by_symbol = {
            event.get("symbol"): event
            for event in events
            if isinstance(event, dict) and event.get("symbol")
        }
        candidates = []
        for symbol in requested:
            event = event_by_symbol.get(symbol, {"status": "UNKNOWN", "symbol": symbol})
            price = (quotes.get("quotes", {}).get(symbol, {}) or {}).get("price")
            forecast = self._call(self.forecasts, symbol, price=price)
            technicals = self._call(self.technicals, symbol)
            news = self._call(self.news, symbol, as_of=as_of)
            short_interest = self._call(self.short_interest, symbol, as_of=as_of)
            insider = self._call(self.insider, symbol, as_of) if self.insider else "UNKNOWN"
            dilution = self._call(self.dilution, symbol, as_of) if self.dilution else "UNKNOWN"
            insider_status = insider.get("status", "UNKNOWN") if isinstance(insider, dict) else insider
            dilution_status = dilution.get("status", "UNKNOWN") if isinstance(dilution, dict) else dilution
            candidates.append(build_candidate(
                symbol=symbol,
                as_of=as_of,
                calendar=event,
                quote=quotes,
                forecast=forecast,
                technicals=technicals,
                news=news,
                short_interest=short_interest,
                insider_status=insider_status,
                dilution_status=dilution_status,
            ))
        return {
            "status": "PASS",
            "as_of": as_of,
            "requested_symbols": requested,
            "removed_duplicate_symbols": removed_duplicate_symbols,
            "calendar": calendar,
            "quotes": quotes,
            "candidates": candidates,
        }


__all__ = ["EarningsPipeline"]

      
