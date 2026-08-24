"""Minimal stateful Streamable-HTTP MCP session for TVRemix."""

from __future__ import annotations


class TvremixMcpSession:
    def __init__(self, *, url: str, headers: dict, requester, timeout: float = 20):
        self.url = url
        self.headers = dict(headers)
        self.requester = requester
        self.timeout = timeout
        self.session_id = None
        self._request_id = 0

    def _request(self, method: str, params: dict):
        self._request_id += 1
        headers = dict(self.headers)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        result = self.requester(self.url, headers, self.timeout, payload)
        if isinstance(result, tuple) and len(result) == 2:
            return result
        if isinstance(result, dict) and "response" in result:
            return result.get("response"), result.get("headers", {})
        return None, {}

    def _initialize(self) -> bool:
        try:
            response, response_headers = self._request(
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "earnings-monitor", "version": "0.1"},
                },
            )
        except Exception:
            return False
        if not isinstance(response, dict) or not isinstance(response.get("result"), dict):
            return False
        self.session_id = response_headers.get("mcp-session-id") if isinstance(response_headers, dict) else None
        return True

    def call_tool(self, name: str, arguments: dict) -> dict:
        if self.session_id is None and not self._initialize():
            return {"status": "UNKNOWN", "response": None, "error": "initialize_failed"}
        try:
            response, _ = self._request(
                "tools/call",
                {"name": name, "arguments": arguments},
            )
        except Exception:
            return {"status": "UNKNOWN", "response": None, "error": "request_failed"}
        return {"status": "PASS", "response": response, "error": None}


__all__ = ["TvremixMcpSession"]

