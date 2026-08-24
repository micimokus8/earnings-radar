"""Wire SEC form-4 and dilution checks into pipeline status lookups."""

from __future__ import annotations

from datetime import date, timedelta

from earnings_monitor.sec_dilution import classify_dilution_filings
from earnings_monitor.sec_form4_collector import collect_form4_activity

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DILUTION_FORMS = {"424B5", "S-3", "S-1"}


def load_ticker_map(client) -> dict:
    raw = client.get_json(COMPANY_TICKERS_URL)
    return {str(entry["ticker"]).upper(): entry for entry in raw.values()}


def resolve_cik(ticker_map: dict, symbol: str):
    ticker = str(symbol).split(":")[-1].strip().upper()
    entry = ticker_map.get(ticker)
    if not entry:
        return None
    return str(int(entry["cik_str"]))


def _submissions_url(cik: str) -> str:
    return f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"


def make_insider_lookup(client, *, ticker_map=None, lookback_days: int = 14):
    if ticker_map is None:
        ticker_map = load_ticker_map(client)

    def lookup(symbol, as_of) -> str:
        cik = resolve_cik(ticker_map, symbol)
        if not cik:
            return "UNKNOWN"
        end = date.fromisoformat(str(as_of)[:10])
        start = end - timedelta(days=lookback_days)
        result = collect_form4_activity(
            client,
            cik=cik,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        return result.get("status", "UNKNOWN")

    return lookup


def make_dilution_lookup(client, *, ticker_map=None):
    if ticker_map is None:
        ticker_map = load_ticker_map(client)

    def lookup(symbol, as_of) -> str:
        cik = resolve_cik(ticker_map, symbol)
        if not cik:
            return "UNKNOWN"
        submissions = client.get_json(_submissions_url(cik))
        recent = submissions["filings"]["recent"]
        fields = ("form", "filingDate", "accessionNumber", "primaryDocument")
        rows = [dict(zip(fields, values)) for values in zip(*(recent[name] for name in fields))]
        filings = [
            {"form": row["form"], "filed": row["filingDate"]}
            for row in rows
            if str(row["form"]).upper() in DILUTION_FORMS
        ]
        return classify_dilution_filings(filings, as_of=str(as_of)[:10])["status"]

    return lookup


__all__ = [
    "COMPANY_TICKERS_URL",
    "load_ticker_map",
    "resolve_cik",
    "make_insider_lookup",
    "make_dilution_lookup",
]

      
