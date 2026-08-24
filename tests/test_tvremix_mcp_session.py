import unittest

from earnings_monitor.tvremix_mcp_session import TvremixMcpSession


class TvremixMcpSessionTests(unittest.TestCase):
    def test_initialize_session_and_call_tool(self):
        calls = []

        def requester(url, headers, timeout, payload):
            calls.append((url, headers, timeout, payload))
            if payload["method"] == "initialize":
                return {"result": {"protocolVersion": "2025-03-26"}}, {"mcp-session-id": "session-1"}
            return {"result": {"ok": True}}, {}

        session = TvremixMcpSession(
            url="https://example.test/mcp",
            headers={"Authorization": "Bearer token"},
            requester=requester,
            timeout=10,
        )
        result = session.call_tool("get_forecasts", {"symbol": "NASDAQ:AAPL"})

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][3]["method"], "initialize")
        self.assertEqual(calls[1][3]["method"], "tools/call")
        self.assertEqual(calls[1][1]["Mcp-Session-Id"], "session-1")

    def test_supports_request_json_result_envelope(self):
        def requester(url, headers, timeout, payload):
            if payload["method"] == "initialize":
                return {
                    "status": 200,
                    "response": {"result": {"protocolVersion": "2025-03-26"}},
                    "headers": {"mcp-session-id": "session-2"},
                }
            return {
                "status": 200,
                "response": {"result": {"ok": True}},
                "headers": {},
            }

        session = TvremixMcpSession(
            url="https://example.test/mcp",
            headers={},
            requester=requester,
        )
        result = session.call_tool("get_forecasts", {"symbol": "AAPL"})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["response"], {"result": {"ok": True}})

    def test_session_id_is_optional_when_initialize_succeeds(self):
        def requester(url, headers, timeout, payload):
            return {"response": {"result": {"ok": True}}, "headers": {}}

        session = TvremixMcpSession(url="https://example.test/mcp", headers={}, requester=requester)
        result = session.call_tool("get_forecasts", {"symbol": "AAPL"})
        self.assertEqual(result["status"], "PASS")

    def test_missing_session_id_is_unknown(self):
        def requester(*_args):
            return {"error": {"message": "initialize failed"}}, {}

        session = TvremixMcpSession(
            url="https://example.test/mcp",
            headers={},
            requester=requester,
        )
        result = session.call_tool("get_forecasts", {"symbol": "AAPL"})
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

