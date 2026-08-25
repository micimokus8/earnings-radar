import unittest

from earnings_monitor.dedup import dedupe_dual_class_symbols


class DedupTests(unittest.TestCase):
    def test_collapses_class_suffix_when_common_present(self):
        self.assertEqual(
            dedupe_dual_class_symbols(["NYSE:HEI", "NYSE:HEI.A"]),
            ["NYSE:HEI"],
        )

    def test_keeps_only_one_when_both_suffixed(self):
        self.assertEqual(len(dedupe_dual_class_symbols(["BRK.A", "BRK.B"])), 1)

    def test_prefers_plain_over_suffixed_regardless_of_order(self):
        self.assertEqual(
            dedupe_dual_class_symbols(["NYSE:HEI.A", "NYSE:HEI"]),
            ["NYSE:HEI"],
        )

    def test_unrelated_symbols_untouched_and_ordered(self):
        self.assertEqual(
            dedupe_dual_class_symbols(
                ["NASDAQ:SMTC", "NYSE:BOX", "NYSE:HEI.A", "NYSE:HEI"]
            ),
            ["NASDAQ:SMTC", "NYSE:BOX", "NYSE:HEI"],
        )

    def test_no_duplicates_unchanged(self):
        self.assertEqual(
            dedupe_dual_class_symbols(["A", "B", "C"]),
            ["A", "B", "C"],
        )


if __name__ == "__main__":
    unittest.main()
