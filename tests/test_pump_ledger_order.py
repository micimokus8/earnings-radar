import importlib.util
import unittest
from datetime import date
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pump_ledger.py"
_spec = importlib.util.spec_from_file_location("pump_ledger", _SCRIPT)
assert _spec is not None and _spec.loader is not None
pump_ledger = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pump_ledger)


def _sym(*dates):
    return [{"report_date": d, "symbol": "X"} for d in dates]


class TestResolveOrder(unittest.TestCase):
    TODAY = date(2026, 11, 13)

    def test_fresh_first_then_backlog_oldest_first(self):
        by_sym = {
            "FRESH_NEW": _sym("2026-11-12"),   # age 1
            "FRESH_OLD": _sym("2026-11-09"),   # age 4
            "OLD_STAR": _sym("2026-09-29"),    # age 45
            "OLD_LESS": _sym("2026-10-28"),    # age 16
        }
        self.assertEqual(
            pump_ledger._resolve_order(by_sym, today=self.TODAY),
            ["FRESH_NEW", "FRESH_OLD", "OLD_STAR", "OLD_LESS"],
        )

    def test_boundary_day_is_still_fresh(self):
        by_sym = {
            "BOUNDARY": _sym("2026-11-08"),    # age 5 == FRESH_DAYS -> fresh
            "BACKLOG": _sym("2026-11-07"),     # age 6 -> backlog
        }
        self.assertEqual(
            pump_ledger._resolve_order(by_sym, today=self.TODAY),
            ["BOUNDARY", "BACKLOG"],
        )

    def test_symbol_age_uses_newest_report_date(self):
        # A symbol with an old snapshot AND a fresh one must count as fresh.
        by_sym = {
            "MIXED": _sym("2026-09-01", "2026-11-12"),
            "PLAIN_OLD": _sym("2026-10-01"),
        }
        order = pump_ledger._resolve_order(by_sym, today=self.TODAY)
        self.assertEqual(order, ["MIXED", "PLAIN_OLD"])

    def test_the_stuck_tail_actually_drains(self):
        # The reported bug: a big backlog must be reached, not starved.
        by_sym = {f"OLD{i:03d}": _sym("2026-09-%02d" % (i % 28 + 1)) for i in range(20)}
        by_sym["NEWEST"] = _sym("2026-11-12")
        order = pump_ledger._resolve_order(by_sym, today=self.TODAY)
        self.assertEqual(order[0], "NEWEST")
        # every backlog symbol appears exactly once, and the tail is ordered oldest-first
        self.assertEqual(set(order), set(by_sym))
        backlog = order[1:]
        dates = [min(s["report_date"] for s in by_sym[s]) for s in backlog]
        self.assertEqual(dates, sorted(dates))


if __name__ == "__main__":
    unittest.main()
