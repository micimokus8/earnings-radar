from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


class ReportState:
    def __init__(self):
        self._reports = {}
        self._active = {}

    def start(self, report_type: str, *, report_date: str) -> dict:
        if report_type not in {"BEFORE_OPEN", "AFTER_CLOSE"}:
            raise ValueError("unsupported report type")
        report = {
            "report_id": f"{report_date}:{report_type}:{uuid4().hex}",
            "report_type": report_type,
            "report_date": report_date,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._reports[report["report_id"]] = report
        self._active[report_type] = report["report_id"]
        return report

    def active_report(self, report_type: str):
        report_id = self._active.get(report_type)
        return self._reports.get(report_id) if report_id else None

    def get(self, report_id: str):
        return self._reports.get(report_id)

    def cleanup(self, report_type: str):
        for report_id, report in list(self._reports.items()):
            if report["report_type"] == report_type:
                del self._reports[report_id]
        self._active.pop(report_type, None)
