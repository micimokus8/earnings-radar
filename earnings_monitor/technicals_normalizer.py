"""Map verified technicals/OHLCV output to deterministic score fields."""

from __future__ import annotations

from earnings_monitor.indicators import calculate_adx, calculate_ema


_FIELDS = (
    "price_1d", "price_4h", "ema20_1d", "ema20_4h", "ema50_1d",
    "rsi_1d", "adx_1d",
)


def normalize_technicals_for_score(result: dict) -> dict:
    values = {field: None for field in _FIELDS}
    unknown = []
    if not isinstance(result, dict) or result.get("status") != "PASS":
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

    return {
        "status": "PASS" if not unknown else "PARTIAL",
        "values": values,
        "unknown": unknown,
    }


__all__ = ["normalize_technicals_for_score"]

