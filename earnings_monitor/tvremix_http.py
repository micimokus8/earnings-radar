"""Minimal JSON HTTPS requester for the TVRemix MCP endpoint."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


def request_json(url, headers, timeout, payload, *, opener=urllib.request.urlopen,
                 retries: int = 0, backoff_seconds: float = 0.5,
                 max_backoff: float = 4.0,
                 sleep=time.sleep):
    """POST JSON with calm, 429-aware retry/backoff for the TVRemix MCP.

    Rate-limit bursts are the dominant failure mode; keep backoff gentle and
    honor a server-supplied Retry-After when present.
    """
    _TRANSIENT = {429, 500, 502, 503, 504}
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={**headers, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        method="POST",
    )
    last_error = None
    status = None
    raw = b""
    response_headers = {}
    for attempt in range(retries + 1):
        try:
            with opener(request, timeout=timeout) as response:
                status = getattr(response, "status", None)
                raw = response.read()
                response_headers = dict(response.headers)
        except urllib.error.HTTPError as exc:
            status = int(getattr(exc, "code", 0) or 0)
            raw = b""
            response_headers = dict(getattr(exc, "headers", {}) or {})
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = RuntimeError("tvremix_transport_failed")
            status = None
        if status is not None and status in _TRANSIENT:
            last_error = RuntimeError(f"tvremix_http_{status}")
            if attempt < retries:
                retry_after = _retry_after(response_headers)
                delay = retry_after if retry_after is not None \
                    else min(max_backoff, backoff_seconds * (2 ** attempt))
                sleep(delay)
                continue
            raise last_error
        if status is None:
            if attempt < retries:
                sleep(min(max_backoff, backoff_seconds * (2 ** attempt)))
                continue
            raise last_error or RuntimeError("tvremix_transport_failed")
        break  # real (non-transient) status received

    if status is None or status < 200 or status >= 300:
        raise RuntimeError(f"tvremix_http_{status}")
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("tvremix_invalid_json") from exc
    return {"status": status, "response": decoded, "headers": response_headers}


def _retry_after(headers: dict):
    for key, value in headers.items():
        if str(key).lower() == "retry-after":
            try:
                return max(0.0, float(value))
            except (TypeError, ValueError):
                return None
    return None


__all__ = ["request_json"]

