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


def calculate_macd(values, fast: int = 12, slow: int = 26, signal: int = 9):
    """Return the latest MACD line, signal line and histogram."""
    if min(fast, slow, signal) <= 0 or fast >= slow:
        raise ValueError("MACD periods must satisfy 0 < fast < slow")
    closes = [float(value) for value in values]
    if len(closes) < slow + signal - 1:
        return None
    fast_ema = calculate_ema(closes, fast)
    slow_ema = calculate_ema(closes, slow)
    macd = [None if f is None or s is None else f - s
            for f, s in zip(fast_ema, slow_ema)]
    compact = [value for value in macd if value is not None]
    signal_values = calculate_ema(compact, signal)
    line, signal_line = macd[-1], signal_values[-1]
    return {"line": line, "signal": signal_line, "histogram": line - signal_line}


def high_52w(bars, lookback: int = 252):
    """Highest high in the last *lookback* bars (default 252 trading days)."""
    if not bars or len(bars) < 2:
        return None
    window = bars[-min(lookback, len(bars)):]
    try:
        return max(float(bar["h"]) for bar in window)
    except (KeyError, TypeError, ValueError):
        return None


def recent_high(bars, lookback: int = 60):
    """Highest high in the last *lookback* bars (resistance proxy)."""
    return high_52w(bars, lookback=lookback)


def daily_change_pct(bars):
    """Percent change of the last close vs the previous close."""
    if not bars or len(bars) < 2:
        return None
    try:
        prev = float(bars[-2]["c"])
        last = float(bars[-1]["c"])
    except (KeyError, TypeError, ValueError):
        return None
    if prev == 0:
        return None
    return (last - prev) / prev * 100.0


def change_pct(bars, lookback: int = 5):
    """Percent change of the last close vs the close *lookback* bars ago."""
    if not bars or len(bars) < lookback + 1:
        return None
    try:
        old = float(bars[-(lookback + 1)]["c"])
        last = float(bars[-1]["c"])
    except (KeyError, TypeError, ValueError):
        return None
    if old == 0:
        return None
    return (last - old) / old * 100.0


def distance_to_high_pct(price, high_value):
    """Negative percentage: how far below *high_value* the *price* is."""
    if price is None or high_value is None or high_value == 0:
        return None
    return (price - high_value) / high_value * 100.0


__all__ = [
    "calculate_ema", "calculate_adx", "calculate_macd",
    "high_52w", "recent_high", "daily_change_pct", "change_pct",
    "distance_to_high_pct",
]

