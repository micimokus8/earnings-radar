"""Minimal JSON HTTPS requester for the TVRemix MCP endpoint."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


def request_json(url, headers, timeout, payload, *, opener=urllib.request.urlopen):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={**headers, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            raw = response.read()
            response_headers = dict(response.headers)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"tvremix_http_{exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("tvremix_transport_failed") from exc

    if status is None or status < 200 or status >= 300:
        raise RuntimeError(f"tvremix_http_{status}")
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("tvremix_invalid_json") from exc
    return {"status": status, "response": decoded, "headers": response_headers}


__all__ = ["request_json"]

