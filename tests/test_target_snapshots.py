import tempfile
import unittest
from pathlib import Path

from earnings_monitor.target_snapshots import TargetSnapshotStore


class TargetSnapshotTests(unittest.TestCase):
    def test_saves_and_reads_latest_snapshot_within_window(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TargetSnapshotStore(Path(directory) / "targets.json")
            store.save("ABC", 100.0, "2026-08-01T10:00:00+00:00")
            result = store.previous("ABC", "2026-08-12T10:00:00+00:00")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["average"], 100.0)

    def test_expired_snapshot_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TargetSnapshotStore(Path(directory) / "targets.json")
            store.save("ABC", 100.0, "2026-07-01T10:00:00+00:00")
            result = store.previous("ABC", "2026-08-12T10:00:00+00:00")
            self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

__all__ = ["TargetSnapshotTests"]


