"""Network-free replay of the earnings pipeline from fixture files."""

from __future__ import annotations

import json

from earnings_monitor.pipeline import EarningsPipeline
from earnings_monitor.run_report import run_report


class ReplayCalendarClient:
    def __init__(self, payload: dict):
        self.payload = payload

    def get(self, *, symbols=None, date_from=None, date_to=None):
        return self.payload


class ReplayQuotesClient:
    def __init__(self, payload: dict):
        self.payload = payload

    def get(self, symbols):
        return self.payload


class ReplaySymbolClient:
    """Static per-symbol client for forecasts/technicals/news/short interest."""

    def __init__(self, payloads: dict):
        self.payloads = payloads

    def get(self, symbol, **kwargs):
        return self.payloads.get(symbol, {"status": "UNKNOWN"})


def _static_status(mapping: dict):
    def lookup(symbol, as_of):
        return mapping.get(symbol, "UNKNOWN")

    return lookup


def build_replay_pipeline(fixture: dict) -> EarningsPipeline:
    return EarningsPipeline(
        calendar=ReplayCalendarClient(fixture["calendar"]),
        quotes=ReplayQuotesClient(fixture["quotes"]),
        forecasts=ReplaySymbolClient(fixture.get("forecasts", {})),
        technicals=ReplaySymbolClient(fixture.get("technicals", {})),
        news=ReplaySymbolClient(fixture.get("news", {})),
        short_interest=ReplaySymbolClient(fixture.get("short_interest", {})),
        insider=_static_status(fixture.get("insider_status", {})),
        dilution=_static_status(fixture.get("dilution_status", {})),
    )


def run_fixture_report(fixture_path: str) -> dict:
    with open(fixture_path, encoding="utf-8") as handle:
        fixture = json.load(handle)
    pipeline = build_replay_pipeline(fixture)
    return run_report(
        pipeline,
        symbols=fixture["symbols"],
        report_type=fixture["report_type"],
        report_date=fixture["report_date"],
        as_of=fixture["as_of"],
    )


__all__ = [
    "ReplayCalendarClient",
    "ReplayQuotesClient",
    "ReplaySymbolClient",
    "build_replay_pipeline",
    "run_fixture_report",
]

      
