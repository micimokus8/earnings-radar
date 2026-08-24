from __future__ import annotations

import gzip
import json
from urllib.parse import urljoin, urlparse


def decode_sec_payload(raw: bytes, *, content_encoding: str | None, as_json: bool):
    try:
        data = gzip.decompress(raw) if (content_encoding or "").lower() == "gzip" else raw
        text = data.decode("utf-8")
        return json.loads(text) if as_json else text
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("invalid SEC payload") from exc


def normalize_cik(cik: str | int) -> str:
    value = str(cik).strip()
    if not value.isdigit() or len(value) > 10:
        raise ValueError("CIK must contain at most 10 digits")
    return value.zfill(10)


def resolve_form4_xml_url(
    filing_url: str,
    *,
    primary_document: str,
    directory_listing: list[str],
) -> str:
    if urlparse(primary_document).scheme in {"http", "https"}:
        candidate = primary_document
    else:
        candidate = urljoin(filing_url, primary_document)
    if "/xsl" not in candidate.lower():
        return candidate

    xml_names = [
        item for item in directory_listing
        if item.lower().endswith(".xml")
        and not any(part.lower().startswith("xsl") for part in item.split("/"))
    ]
    if not xml_names:
        raise ValueError("ownership XML link not found")
    return urljoin(filing_url, xml_names[0])


__all__ = ["decode_sec_payload", "normalize_cik", "resolve_form4_xml_url"]
