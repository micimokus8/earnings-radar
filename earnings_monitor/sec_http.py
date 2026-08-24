from __future__ import annotations

import gzip
import json
import time
import urllib.request
from typing import Callable


class SecHttpError(RuntimeError):
    pass


def _default_transport(url: str, *, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "status": response.status,
                "headers": dict(response.headers.items()),
                "body": response.read(),
            }
    except Exception as exc:
        raise exc


class SecHttpClient:
    def __init__(
        self,
        *,
        user_agent: str,
        transport: Callable = _default_transport,
        timeout: float = 20,
        retries: int = 2,
        backoff_seconds: float = 0.5,
    ):
        if not user_agent or not user_agent.strip():
            raise ValueError("SEC User-Agent is required")
        self.user_agent = user_agent.strip()
        self.transport = transport
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff_seconds = max(0.0, backoff_seconds)

    def get_json(self, url: str) -> dict:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip",
        }
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                response = self.transport(url, headers=headers, timeout=self.timeout)
                status = int(response.get("status", 0))
                if status == 200:
                    body = response.get("body", b"")
                    encoding = str(response.get("headers", {}).get("Content-Encoding", "")).lower()
                    if encoding == "gzip":
                        body = gzip.decompress(body)
                    return json.loads(body.decode("utf-8"))
                if status not in {429, 500, 502, 503, 504}:
                    raise SecHttpError(f"SEC HTTP status {status}")
                last_error = SecHttpError(f"SEC transient HTTP status {status}")
            except SecHttpError:
                raise
            except Exception as exc:
                last_error = exc
            if attempt < self.retries and self.backoff_seconds:
                time.sleep(self.backoff_seconds * (2**attempt))
        raise SecHttpError("SEC request failed after retries") from last_error


__all__ = ["SecHttpClient", "SecHttpError"]
