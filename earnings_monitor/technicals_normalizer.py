"""Map verified technicals/OHLCV output to deterministic score fields."""

from __future__ import annotations

from earnings_monitor.indicators import (
    calculate_adx, calculate_ema, calculate_macd,
    high_52w, recent_high, daily_change_pct, change_pct,
    distance_to_high_pct,
)

_FIELDS = (
    "price_1d", "price_4h", "ema20_1d", "ema20_4h", "ema50_1d",
    "rsi_1d", "adx_1d", "macd_1d", "macd_signal_1d", "macd_histogram_1d",
    "high_52w", "recent_high_60d", "daily_change_pct", "change_5d_pct",
    "distance_to_52w_pct",
)


def normalize_technicals_for_score(result: dict) -> dict:
    values = {field: None for field in _FIELDS}
    unknown = []
    if not isinstance(result, dict) or result.get("status") == "UNKNOWN":
        unknown.append("client_status")
        return {"status": "UNKNOWN", "values": values, "unknown": unknown}

    technicals = result.get("technicals")
    ohlcv = result.get("ohlcv")
    if not isinstance(technicals, dict):
        unknown.append("technicals")
    if not isinstance(ohlcv, dict):
        unknown.append("ohlcv")

    for interval, suffix in (("1D", "1d"), ("4h", "4h")):
        current = technicals.get(interval) if isinstance(technicals, dict) else None
        if not isinstance(current, dict):
            unknown.append(f"technicals_{suffix}")
            continue
        price = current.get("price")
        rsi = current.get("rsi")
        if isinstance(price, (int, float)):
            values[f"price_{suffix}"] = price
        else:
            unknown.append(f"price_{suffix}")
        if suffix == "1d":
            if isinstance(rsi, (int, float)):
                values["rsi_1d"] = rsi
            else:
                unknown.append("rsi_1d")

        current_ohlcv = ohlcv.get(interval) if isinstance(ohlcv, dict) else None
        bars = current_ohlcv.get("bars") if isinstance(current_ohlcv, dict) else None
        if not isinstance(bars, list) or not bars:
            unknown.append(f"ohlcv_{suffix}")
            continue
        closes = [bar.get("c") for bar in bars if isinstance(bar, dict)]
        ema20 = calculate_ema(closes, 20)[-1] if closes else None
        if ema20 is not None:
            values[f"ema20_{suffix}"] = ema20
        else:
            unknown.append(f"ema20_{suffix}")
        if suffix == "1d":
            ema50 = calculate_ema(closes, 50)[-1] if closes else None
            values["ema50_1d"] = ema50
            if ema50 is None:
                unknown.append("ema50_1d")
            adx = calculate_adx(bars, 14)
            values["adx_1d"] = adx
            if adx is None:
                unknown.append("adx_1d")
            macd = calculate_macd(closes)
            if macd is None:
                unknown.extend(["macd_1d", "macd_signal_1d", "macd_histogram_1d"])
            else:
                values["macd_1d"] = macd["line"]
                values["macd_signal_1d"] = macd["signal"]
                values["macd_histogram_1d"] = macd["histogram"]

            # Earnings-hunt metrics: 52w high, resistance proxy, run-up
            h52 = high_52w(bars)
            values["high_52w"] = h52
            if h52 is None:
                unknown.append("high_52w")
            rh = recent_high(bars, 60)
            values["recent_high_60d"] = rh
            if rh is None:
                unknown.append("recent_high_60d")
            dcp = daily_change_pct(bars)
            values["daily_change_pct"] = dcp
            if dcp is None:
                unknown.append("daily_change_pct")
            c5 = change_pct(bars, 5)
            values["change_5d_pct"] = c5
            if c5 is None:
                unknown.append("change_5d_pct")
            price_1d = values.get("price_1d")
            dist52 = distance_to_high_pct(price_1d, h52)
            values["distance_to_52w_pct"] = dist52
            if dist52 is None:
                unknown.append("distance_to_52w_pct")

    return {
        "status": "PASS" if not unknown else "PARTIAL",
        "values": values,
        "unknown": unknown,
    }


__all__ = ["normalize_technicals_for_score"]

