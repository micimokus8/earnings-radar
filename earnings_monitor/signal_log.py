"""Append every rendered candidate to the ledger. Idempotent per date/session/symbol."""

from __future__ import annotations

import json

from earnings_monitor.paths import ledger_dir


def _features(candidate: dict) -> dict:
    values = candidate.get("values") or {}
    score = candidate.get("score") or {}
    return {
        "rsi": values.get("rsi_1d"),
        "stoch_k": values.get("stoch_k_1d"),
        "adx": values.get("adx_1d"),
        "short_pct": values.get("short_pct_outstanding"),
        "days_to_cover": values.get("days_to_cover"),
        "change_5d_pct": values.get("change_5d_pct"),
        "daily_change_pct": values.get("daily_change_pct"),
        "distance_to_52w_pct": score.get("distance_to_52w_pct", values.get("distance_to_52w_pct")),
        "room_to_resistance_pct": score.get("room_to_resistance_pct", values.get("room_to_resistance_pct")),
        "beat_rate": values.get("beat_rate"),
        "beat_n": values.get("beat_n"),
        "hist_reaction_pct": values.get("hist_reaction_pct"),
        "analyst_revision": values.get("analyst_revision"),
        "target_revision": values.get("target_revision"),
        "positive_news_count": values.get("positive_news_count"),
        "news_severity": values.get("news_severity"),
        "technical_points": score.get("technical_points"),
        "total_points": score.get("total_points"),
        "blocked": score.get("blocked"),
        "skip_reason": score.get("skip_reason"),
    }


def record_report(report: dict) -> int:
    """Store one row per candidate. Returns how many new rows were appended."""
    ledger = ledger_dir()
    path = ledger / "snapshots.jsonl"
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            existing.add((row.get("report_date"), row.get("report_type"), row.get("symbol")))
    theses = {}
    thesis_path = ledger / "theses" / f"{report.get('report_date')}_{report.get('report_type')}.json"
    if thesis_path.exists():
        try:
            theses = json.loads(thesis_path.read_text(encoding="utf-8")).get("theses", {})
        except (OSError, json.JSONDecodeError):
            theses = {}
    added = 0
    fresh = []
    with path.open("a", encoding="utf-8") as handle:
        for candidate in report.get("candidates") or []:
            symbol = str(candidate.get("symbol", "")).split(":")[-1].strip()
            if not symbol:
                continue
            key = (report.get("report_date"), report.get("report_type"), symbol)
            if key in existing:
                continue
            values = candidate.get("values") or {}
            score = candidate.get("score") or {}
            row = {
                "report_date": report.get("report_date"),
                "report_type": report.get("report_type"),
                "symbol": symbol,
                "entry_price": values.get("price") or values.get("price_1d"),
                "completed_close": values.get("price_1d"),
                "priced_at": report.get("priced_at"),
                "preselect_price": candidate.get("preselect_price"),
                "drift_pct": candidate.get("drift_pct"),
                "label": score.get("label"),
                "score_pct": score.get("score_pct"),
                "total_points": score.get("total_points"),
                "technical_points": score.get("technical_points"),
                "horizon": report.get("horizon"),
                "thesis": theses.get(symbol),
                "features": _features(candidate),
            }
            line = json.dumps(row, ensure_ascii=False)
            handle.write(line + "\n")
            fresh.append(line)
            existing.add(key)
            added += 1
    if fresh:
        with (ledger / "signals.jsonl").open("a", encoding="utf-8") as handle:
            for line in fresh:
                handle.write(line + "\n")
    return added


__all__ = ["record_report"]
