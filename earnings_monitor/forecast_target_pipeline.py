"""Deterministic bridge between forecast responses and target history."""

from __future__ import annotations

from pathlib import Path

from earnings_monitor.target_snapshots import TargetSnapshotStore
from earnings_monitor.targets import detect_target_cut


def evaluate_target_change(*, store_path: Path, symbol: str, forecast: dict, as_of: str) -> dict:
    targets = forecast.get("price_targets") if isinstance(forecast, dict) else None
    current = targets.get("average") if isinstance(targets, dict) else None
    store = TargetSnapshotStore(store_path)
    previous = store.previous(symbol, as_of)
    if not isinstance(current, (int, float)):
        return {
            "status": "UNKNOWN",
            "cut": None,
            "previous_average": previous["average"],
            "current_average": None,
        }
    comparison = detect_target_cut(
        previous_average=previous["average"],
        current_average=current,
    )
    store.save(symbol, current, as_of)
    return {
        "status": comparison["status"],
        "cut": comparison["cut"],
        "change_pct": comparison["change_pct"],
        "previous_average": previous["average"],
        "current_average": current,
    }


__all__ = ["evaluate_target_change"]
