from __future__ import annotations

from datetime import date

from .sec_adapter import normalize_cik, resolve_form4_xml_url
from .sec_form4 import summarize_transactions, parse_form4_xml


def _archive_base(cik: str, accession: str) -> str:
    numeric = str(int(cik))
    accession_no_dashes = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{numeric}/{accession_no_dashes}/"


def collect_form4_activity(client, *, cik, start_date: str, end_date: str) -> dict:
    try:
        normalized_cik = normalize_cik(cik)
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        submissions = client.get_json(
            f"https://data.sec.gov/submissions/CIK{normalized_cik}.json"
        )
        recent = submissions["filings"]["recent"]
        fields = ("form", "filingDate", "accessionNumber", "primaryDocument")
        rows = [dict(zip(fields, values)) for values in zip(*(recent[name] for name in fields))]
        filings = [
            row for row in rows
            if row["form"] == "4"
            and start <= date.fromisoformat(row["filingDate"]) <= end
        ]
        all_transactions = []
        filings_failed = 0
        for row in filings:
            try:
                filing_base = _archive_base(normalized_cik, row["accessionNumber"])
                listing = getattr(client, "get_directory_listing", lambda _url: ["form4.xml"])(filing_base)
                xml_url = resolve_form4_xml_url(
                    filing_base,
                    primary_document=row["primaryDocument"],
                    directory_listing=listing,
                )
                all_transactions.extend(parse_form4_xml(client.get_text(xml_url)))
            except Exception:
                filings_failed += 1
        summary = summarize_transactions(all_transactions)
        if not filings:
            status = "NO_RECENT_FILING_FOUND"
        elif filings_failed:
            status = "PARTIAL"
        else:
            status = summary["status"]
        return {
            **summary,
            "filings_checked": len(filings),
            "filings_failed": filings_failed,
            "status": status,
        }
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "sell_flag": False,
            "sell_shares": 0,
            "codes": [],
            "filings_checked": 0,
            "error": type(exc).__name__,
        }


__all__ = ["collect_form4_activity"]
