"""Repository-relative data paths. Directories stay gitignored."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_root() -> Path:
    override = os.environ.get("EARNINGS_DATA_DIR", "").strip()
    root = Path(override) if override else repo_root() / "data"
    return root


def reports_dir() -> Path:
    path = data_root() / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ledger_dir() -> Path:
    path = data_root() / "ledger"
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["repo_root", "data_root", "reports_dir", "ledger_dir"]
