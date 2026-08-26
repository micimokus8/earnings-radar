"""Deterministic report construction for one earnings scan stream."""

from __future__ import annotations

from collections import Counter


def build_report(
    *,
    report_type: str,
    report_date: str,
    as_of: str,
    candidates: list[dict],
    removed_duplicate_symbols: list[str] | None = None,
    truncated: bool = False,
) -> dict:
    if report_type not in {"BEFORE_OPEN", "AFTER_CLOSE"}:
        raise ValueError("unsupported report type")

    ordered = sorted(
        candidates,
        key=lambda row: (
            -(row.get("score", {}).get("total_points") or 0),
            row.get("symbol", ""),
        ),
    )
    missing_fields = Counter(
        field
        for candidate in ordered
        for field in candidate.get("missing", [])
    )
    incomplete_count = sum(
        candidate.get("status") == "INCOMPLETE" for candidate in ordered
    )

    return {
        "report_id": f"{report_date}:{report_type}",
        "report_type": report_type,
        "report_date": report_date,
        "as_of": as_of,
        "candidates": ordered,
        "quality": {
            "candidate_count": len(ordered),
            "incomplete_count": incomplete_count,
            "missing_fields": dict(sorted(missing_fields.items())),
            "removed_duplicate_symbols": list(removed_duplicate_symbols or []),
            "truncated": bool(truncated),
        },
    }


def merge_reports(
    reports: list[dict],
    *,
    report_type: str | None = None,
    report_date: str | None = None,
    as_of: str | None = None,
) -> dict:
    """Combine several shard reports into one (no symbols dropped)."""
    if not reports:
        raise ValueError("no reports to merge")

    seen = set()
    candidates: list[dict] = []
    removed: list[str] = []
    truncated = False
    for report in reports:
        for candidate in report.get("candidates", []):
            symbol = candidate.get("symbol")
            if symbol in seen:
                continue
            seen.add(symbol)
            candidates.append(candidate)
        quality = report.get("quality", {})
        removed.extend(quality.get("removed_duplicate_symbols", []) or [])
        truncated = truncated or bool(quality.get("truncated", False))

    first = reports[0]
    return build_report(
        report_type=report_type or first["report_type"],
        report_date=report_date or first["report_date"],
        as_of=as_of or first["as_of"],
        candidates=candidates,
        removed_duplicate_symbols=removed,
        truncated=truncated,
    )


__all__ = ["build_report", "merge_reports"]

      
  