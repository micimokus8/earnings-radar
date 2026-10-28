import importlib.util
import subprocess
import time
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_sharded.py"
_spec = importlib.util.spec_from_file_location("run_sharded", _SCRIPT)
assert _spec is not None and _spec.loader is not None
run_sharded = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_sharded)


class _HangingProc:
    """Popen-Ersatz, der nie fertig wird und kill() respektiert."""

    def __init__(self):
        self.killed = False

    def wait(self, timeout: float = 0.0):
        # Ein echter Popen kehrt nach kill() sofort zurueck. Der Fake muss das
        # nachbilden, sonst misst der Test die 6s-Sicherheitswartezeit.
        if self.killed:
            return -9
        if timeout:
            time.sleep(timeout)
        if self.killed:
            return -9
        raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)

    def kill(self):
        self.killed = True

    def poll(self):
        return -9 if self.killed else None


class SharedDeadlineTests(unittest.TestCase):
    def test_all_processes_share_one_deadline(self):
        # Der Bug: 3 Chunks x 280s = 840s > 600s Cron-Timeout. Mit einer
        # gemeinsamen Deadline darf die Summe nicht mit der Anzahl wachsen.
        procs = [_HangingProc() for _ in range(6)]
        start = time.monotonic()
        run_sharded._wait_all(procs, deadline=0.4)
        elapsed = time.monotonic() - start

        self.assertTrue(all(p.killed for p in procs))
        self.assertLess(elapsed, 0.9, f"6 Prozesse brauchten {elapsed:.2f}s — Deadline nicht geteilt")


class ChunkBudgetTests(unittest.TestCase):
    def test_per_chunk_is_used_when_budget_allows(self):
        self.assertEqual(
            run_sharded._effective_chunk_deadline(280, budget_end=1000, now=0), 280)

    def test_budget_caps_the_chunk_deadline(self):
        # 540s Budget, 30s verbraucht, 100s Reserve -> 410s frei fuer Chunks,
        # per-chunk 280 bleibt also erhalten.
        self.assertEqual(
            run_sharded._effective_chunk_deadline(280, budget_end=540, now=30), 280)

    def test_tight_budget_shrinks_the_chunk_deadline(self):
        # 540s Budget, 400s verbraucht -> 140s minus Reserve = 40s -> Floor 60s.
        self.assertEqual(
            run_sharded._effective_chunk_deadline(280, budget_end=540, now=400), 60)


class InterpretMergedTests(unittest.TestCase):
    def _merged(self, labelled=True):
        score = {"label": "SKIP"} if labelled else {"label": None}
        return {"candidates": [{"symbol": "NASDAQ:ZM", "score": score}]}

    def test_disabled_by_flag_file(self):
        calls = []
        d, e, note = run_sharded._interpret_merged(
            self._merged(), enabled="OFF", api_key="k", model="m",
            base_url="https://x", interpreter=lambda *a, **kw: calls.append(1) or {})
        self.assertEqual((d, e), ({}, ""))
        self.assertIn("deaktiviert", note)
        self.assertEqual(calls, [])

    def test_missing_key_skips_call(self):
        calls = []
        d, e, note = run_sharded._interpret_merged(
            self._merged(), enabled="ON", api_key="", model="m",
            base_url="https://x", interpreter=lambda *a, **kw: calls.append(1) or {})
        self.assertIn("kein Key", note)
        self.assertEqual(calls, [])

    def test_no_labelled_candidates_skips_call(self):
        calls = []
        d, e, note = run_sharded._interpret_merged(
            self._merged(labelled=False), enabled="ON", api_key="k", model="m",
            base_url="https://x", interpreter=lambda *a, **kw: calls.append(1) or {})
        self.assertIn("keine bewertbaren", note)
        self.assertEqual(calls, [])

    def test_result_is_passed_through_and_capped_at_five(self):
        seen = {}

        def fake(candidates, *, api_key, base_url, model):
            seen["n"] = len(candidates)
            seen["model"] = model
            return {"deutung": {"NASDAQ:ZM": "ok"}, "empfehlung": "Top 1"}

        merged = {"candidates": [
            {"symbol": f"S{i}", "score": {"label": "BUY"}} for i in range(8)
        ]}
        d, e, note = run_sharded._interpret_merged(
            merged, enabled="ON", api_key="k", model="z-ai/glm-5.3-flash",
            base_url="https://x", interpreter=fake)
        self.assertEqual(d, {"NASDAQ:ZM": "ok"})
        self.assertEqual(e, "Top 1")
        self.assertEqual(seen["n"], 5)
        self.assertIn("glm-5.3-flash", note)

    def test_failure_reports_error(self):
        def fake(*a, **kw):
            return {"deutung": {}, "empfehlung": "", "error": "boom"}

        d, e, note = run_sharded._interpret_merged(
            self._merged(), enabled="ON", api_key="k", model="m",
            base_url="https://x", interpreter=fake)
        self.assertIn("boom", note)


if __name__ == "__main__":
    unittest.main()
