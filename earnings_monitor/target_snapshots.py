"""Small deterministic JSON-backed analyst-target snapshot store."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


class TargetSnapshotStore:
    def __init__(self, path: Path, max_age_days: int = 14):
        self.path = Path(path)
        self.max_age = timedelta(days=max_age_days)

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def save(self, symbol: str, average: float, observed_at: str) -> None:
        data = self._read()
        entries = data.setdefault(symbol, [])
        entries.append({"average": average, "observed_at": observed_at})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, sort_keys=True))
        temporary.replace(self.path)

    def previous(self, symbol: str, as_of: str) -> dict:
        try:
            current = datetime.fromisoformat(as_of)
        except ValueError:
            return {"status": "UNKNOWN", "average": None, "observed_at": None}
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        candidates = []
        for entry in self._read().get(symbol, []):
            try:
                observed = datetime.fromisoformat(entry["observed_at"])
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=timezone.utc)
                if observed <= current and current - observed <= self.max_age:
                    candidates.append((observed, entry))
            except (KeyError, TypeError, ValueError):
                continue
        if not candidates:
            return {"status": "UNKNOWN", "average": None, "observed_at": None}
        _, latest = max(candidates, key=lambda item: item[0])
        return {"status": "PASS", "average": latest["average"], "observed_at": latest["observed_at"]}


__all__ = ["TargetSnapshotStore"]
