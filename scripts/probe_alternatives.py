#!/usr/bin/env python3
"""Safe one-symbol provider probe; never prints credentials or response values."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]

def key(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8").strip()

def probe(base: str, endpoint: str, params: dict, token_name: str) -> None:
    params = dict(params)
    params[token_name] = key("Finhub Key.txt") if base.endswith("finnhub.io/api/v1") else key("TwelveData Key.txt")
    url = f"{base}/{endpoint}?{urlencode(params)}"
    try:
        with urlopen(Request(url, headers={"User-Agent": "earnings-monitor-probe/1.0"}), timeout=15) as response:
            status, body = response.status, response.read()
    except HTTPError as exc:
        status, body = exc.code, exc.read()
    except (URLError, TimeoutError) as exc:
        print(endpoint, "TRANSPORT", type(exc).__name__)
        return
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except (TypeError, ValueError):
        payload = None
    if isinstance(payload, dict):
        fields = sorted(k for k in payload if k not in {"token", "apikey"})
        count = len(payload.get("data", [])) if isinstance(payload.get("data"), list) else None
    elif isinstance(payload, list):
        fields = sorted(payload[0].keys()) if payload and isinstance(payload[0], dict) else []
        count = len(payload)
    else:
        fields, count = [], None
    print(endpoint, f"HTTP={status}", f"fields={fields}", f"count={count}")

symbol = (sys.argv[1] if len(sys.argv) > 1 else "AAPL").upper()
finnhub = "https://finnhub.io/api/v1"
for endpoint, params in [
    ("quote", {"symbol": symbol}),
    ("stock/profile2", {"symbol": symbol}),
    ("stock/price-target", {"symbol": symbol}),
    ("stock/recommendation", {"symbol": symbol}),
    ("stock/eps-estimate", {"symbol": symbol, "freq": "quarterly"}),
    ("company-news", {"symbol": symbol, "from": "2026-08-21", "to": "2026-08-28"}),
]:
    probe(finnhub, endpoint, params, "token")
for interval in ("1day", "4h"):
    probe("https://api.twelvedata.com", "time_series", {"symbol": symbol, "interval": interval, "outputsize": 60, "order": "ASC"}, "apikey")
