"""Compose one deterministic report from a pipeline run."""

from __future__ import annotations

from earnings_monitor.report_builder import build_report


def run_report(
    pipeline,
    *,
    symbols,
    report_type: str,
    report_date: str,
    as_of: str,
    date_from=None,
    date_to=None,
    deadline=None,
) -> dict:
    result = pipeline.run(
        symbols,
        as_of=as_of,
        date_from=date_from,
        date_to=date_to,
        deadline=deadline,
    )
    return build_report(
        report_type=report_type,
        report_date=report_date,
        as_of=as_of,
        candidates=result.get("candidates", []),
        removed_duplicate_symbols=result.get("removed_duplicate_symbols", []),
        truncated=result.get("truncated", False),
    )


__all__ = ["run_report"]
