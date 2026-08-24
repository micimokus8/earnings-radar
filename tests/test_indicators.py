import unittest

from earnings_monitor.indicators import calculate_ema, calculate_adx


class IndicatorTests(unittest.TestCase):
    def test_ema_uses_standard_seed_and_multiplier(self):
        values = [10.0, 11.0, 12.0, 13.0]
        result = calculate_ema(values, period=3)
        self.assertEqual(result[:2], [None, None])
        self.assertAlmostEqual(result[2], 11.0)
        self.assertAlmostEqual(result[3], 12.0)

    def test_adx_returns_unknown_until_enough_valid_bars(self):
        bars = [
            {"h": 10.0, "l": 9.0, "c": 9.5},
            {"h": 10.5, "l": 9.2, "c": 10.0},
        ]
        self.assertIsNone(calculate_adx(bars, period=14))

    def test_adx_returns_numeric_for_sufficient_bars(self):
        bars = []
        close = 100.0
        for index in range(40):
            close += 0.5
            bars.append({"h": close + 1.0, "l": close - 1.0, "c": close})
        result = calculate_adx(bars, period=14)
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)


if __name__ == "__main__":
    unittest.main()

