import unittest

from earnings_monitor.symbol_resolution import TvremixSymbolResolver


class Session:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {
            "status": "PASS",
            "response": {"result": {"content": [{"text": __import__("json").dumps({"success": True, "data": {"symbols": self.rows}})}]}},
        }


class SymbolResolutionTests(unittest.TestCase):
    def test_resolves_exchange_from_tvremix_search(self):
        session = Session([
            {"symbol": "NASDAQ:CANG", "description": "Wrong listing"},
            {"symbol": "NYSE:CANG", "description": "Cango Inc."},
        ])
        self.assertEqual(TvremixSymbolResolver(session).resolve("CANG"), "NYSE:CANG")

    def test_resolves_nasdaq_listing(self):
        session = Session([{"symbol": "NASDAQ:SAIC", "description": "SAIC"}])
        self.assertEqual(TvremixSymbolResolver(session).resolve("SAIC"), "NASDAQ:SAIC")

    def test_explicit_exchange_is_preserved(self):
        session = Session([])
        self.assertEqual(TvremixSymbolResolver(session).resolve("NYSE:CANG"), "NYSE:CANG")
        self.assertEqual(session.calls, [])

    def test_unresolved_symbol_fails_closed(self):
        session = Session([])
        self.assertEqual(TvremixSymbolResolver(session).resolve("UNKNOWN"), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
