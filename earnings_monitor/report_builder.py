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


__all__ = ["build_report"]

      
  