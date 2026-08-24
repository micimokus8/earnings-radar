"""Pure technical indicators calculated from OHLCV bars."""

from __future__ import annotations


def calculate_ema(values, period: int):
    if period <= 0:
        raise ValueError("period must be positive")
    result = [None] * len(values)
    if len(values) < period:
        return result
    try:
        seed = sum(float(value) for value in values[:period]) / period
    except (TypeError, ValueError):
        return result
    result[period - 1] = seed
    multiplier = 2.0 / (period + 1)
    previous = seed
    for index in range(period, len(values)):
        try:
            current = float(values[index])
        except (TypeError, ValueError):
            return result
        previous = (current - previous) * multiplier + previous
        result[index] = previous
    return result


def calculate_adx(bars, period: int = 14):
    if period <= 0 or len(bars) < (2 * period):
        return None
    try:
        highs = [float(bar["h"]) for bar in bars]
        lows = [float(bar["l"]) for bar in bars]
        closes = [float(bar["c"]) for bar in bars]
    except (KeyError, TypeError, ValueError):
        return None

    true_ranges = []
    plus_dm = []
    minus_dm = []
    for index in range(1, len(bars)):
        up_move = highs[index] - highs[index - 1]
        down_move = lows[index - 1] - lows[index]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        true_ranges.append(max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        ))

    atr = sum(true_ranges[:period]) / period
    plus = sum(plus_dm[:period]) / period
    minus = sum(minus_dm[:period]) / period
    dx_values = []

    def append_dx(atr_value, plus_value, minus_value):
        if atr_value == 0:
            dx_values.append(0.0)
            return
        plus_di = 100.0 * plus_value / atr_value
        minus_di = 100.0 * minus_value / atr_value
        denominator = plus_di + minus_di
        dx_values.append(0.0 if denominator == 0 else 100.0 * abs(plus_di - minus_di) / denominator)

    append_dx(atr, plus, minus)
    for index in range(period, len(true_ranges)):
        atr = ((atr * (period - 1)) + true_ranges[index]) / period
        plus = ((plus * (period - 1)) + plus_dm[index]) / period
        minus = ((minus * (period - 1)) + minus_dm[index]) / period
        append_dx(atr, plus, minus)

    if len(dx_values) < period:
        return None
    adx = sum(dx_values[:period]) / period
    for dx in dx_values[period:]:
        adx = ((adx * (period - 1)) + dx) / period
    return float(adx)


__all__ = ["calculate_ema", "calculate_adx"]

