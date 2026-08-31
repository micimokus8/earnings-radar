"""
Twelve Data Collector — OHLCV für 1D + 4H, füttert eure bestehende
indicators.py (EMA20/EMA50/ADX/RSI werden weiterhin lokal berechnet,
nur die Rohdatenquelle wechselt von TVRemix zu Twelve Data).

Env: TWELVEDATA_API_KEY
Free Tier: 8 Calls/Min, 800/Tag — für 12 Symbole × 2 Timeframes = 24 Calls,
mit Stagger von 7.5s komfortabel unter dem Limit (~3 Min für alle 12).

Docs: https://twelvedata.com/docs#time-series
"""

import os
import time
import requests
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

TWELVEDATA_BASE = "https://api.twelvedata.com"
STAGGER_SECONDS = 8.0  # 8 Calls/Min Limit -> min. 7.5s Abstand, 8s zur Sicherheit


def _api_key() -> str:
    key = os.getenv("TWELVEDATA_API_KEY", "")
    if not key:
        raise ValueError("TWELVEDATA_API_KEY nicht gesetzt")
    return key


@dataclass
class OHLCVResult:
    candles: list = field(default_factory=list)  # [{"datetime":..., "open":..., "high":..., "low":..., "close":..., "volume":...}, ...]
    interval: str = ""
    error: Optional[str] = None
    retrieved_at: str = ""
    last_candle_ts: Optional[datetime] = None


def get_ohlcv(symbol: str, interval: str = "1day", outputsize: int = 60) -> OHLCVResult:
    """
    interval: "1day" für 1D, "4h" für 4H (Twelve-Data-Syntax)
    outputsize: Anzahl Kerzen — 60 reicht komfortabel für EMA50 + ADX(14)
    """
    retrieved_at = datetime.now(timezone.utc).isoformat()
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": _api_key(),
        "order": "ASC",  # älteste zuerst, wie's die meisten EMA/RSI-Implementierungen erwarten
    }

    try:
        resp = requests.get(f"{TWELVEDATA_BASE}/time_series", params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return OHLCVResult(interval=interval, error=str(e), retrieved_at=retrieved_at)

    if data.get("status") == "error":
        # Twelve Data gibt strukturierte Fehler zurück (z.B. Rate-Limit, ungültiges Symbol)
        return OHLCVResult(interval=interval, error=data.get("message", "unknown error"),
                            retrieved_at=retrieved_at)

    values = data.get("values", [])
    if not values:
        return OHLCVResult(interval=interval, error="empty response", retrieved_at=retrieved_at)

    candles = [
        {
            "datetime": v["datetime"],
            "open": float(v["open"]),
            "high": float(v["high"]),
            "low": float(v["low"]),
            "close": float(v["close"]),
            "volume": float(v.get("volume", 0)),
        }
        for v in values
    ]

    last_ts = datetime.fromisoformat(candles[-1]["datetime"].replace(" ", "T"))
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)

    return OHLCVResult(candles=candles, interval=interval, retrieved_at=retrieved_at,
                        last_candle_ts=last_ts)


def collect_symbol(symbol: str) -> dict:
    """1D + 4H nacheinander mit Stagger — geht direkt in eure indicators.py."""
    ohlcv_1d = get_ohlcv(symbol, interval="1day")
    time.sleep(STAGGER_SECONDS)
    ohlcv_4h = get_ohlcv(symbol, interval="4h")
    time.sleep(STAGGER_SECONDS)
    return {"ohlcv_1d": ohlcv_1d, "ohlcv_4h": ohlcv_4h}


if __name__ == "__main__":
    import sys
    from dataclasses import asdict

    symbols = sys.argv[1:] or ["AAPL"]
    for sym in symbols:
        print(f"\n=== {sym} ===")
        out = collect_symbol(sym)
        for tf, result in out.items():
            n = len(result.candles)
            print(f"  {tf}: {n} Kerzen, error={result.error}, "
                  f"letzte={result.last_candle_ts}")
