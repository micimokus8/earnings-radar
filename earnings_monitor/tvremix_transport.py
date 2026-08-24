"""Small injectable transport boundary for the TVRemix MCP/API endpoint."""

from __future__ import annotations

from pathlib import Path
from typing import Callable


class TvremixTransport:
    def __init__(self, *, secret_path: Path, requester: Callable, timeout: float = 20):
        self.secret_path = Path(secret_path)
        self.requester = requester
        self.timeout = timeout

    def _token(self):
        try:
            token = self.secret_path.read_text().strip()
        except OSError:
            return None
        return token or None

    def call(self, url: str, payload: dict) -> dict:
        token = self._token()
        if not token:
            return {"status": "UNKNOWN", "response": None, "error": "missing_secret"}
        try:
            response = self.requester(
                url,
                {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                self.timeout,
                payload,
            )
        except Exception:
            return {"status": "UNKNOWN", "response": None, "error": "request_failed"}
        return {"status": "PASS", "response": response, "error": None}


__all__ = ["TvremixTransport"]
