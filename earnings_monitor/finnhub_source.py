"""
Finnhub Collector — Forecast (Analyst Rating, Price Target, EPS Estimate) + News.
Ersetzt TVRemix als Quelle für Kategorie ① und ④.

Env: FINNHUB_API_KEY (gleicher Key wie euer bestehender SI-Fallback)
Free Tier: 60 Calls/Min — für 12 Symbole × 3 Calls (rec + target + news) = 36 Calls,
weit unter dem Limit, trotzdem mit kleinem Stagger fahren.

Passt zu eurem bestehenden RetryWrapper-Pattern aus wiring.py.
"""

import os
import time
import requests
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

FINNHUB_BASE = "https://finnhub.io/api/v1"
STAGGER_SECONDS = 1.1  # bleibt konservativ unter 60/min auch bei Retries
NEWS_WINDOW_DAYS = 7


def _api_key() -> str:
    key = os.getenv("FINNHUB_API_KEY", "")
    if not key:
        raise ValueError("FINNHUB_API_KEY nicht gesetzt")
    return key


def _get(endpoint: str, params: dict, timeout: float = 10.0) -> Optional[dict | list]:
    params = {**params, "token": _api_key()}
    try:
        resp = requests.get(f"{FINNHUB_BASE}/{endpoint}", params=params, timeout=timeout)
        if resp.status_code == 429:
            time.sleep(1.0)
            resp = requests.get(f"{FINNHUB_BASE}/{endpoint}", params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        # Bewusst den echten Fehler zurückgeben statt stillem None,
        # damit ihr im Report seht WARUM etwas fehlt, nicht nur DASS.
        return {"_error": str(e)}


@dataclass
class ForecastResult:
    target_average: Optional[float] = None
    target_upside_pct: Optional[float] = None
    eps_estimate: Optional[float] = None
    rating_buy: Optional[int] = None
    rating_hold: Optional[int] = None
    rating_sell: Optional[int] = None
    target_recently_cut: Optional[bool] = None  # None = UNKNOWN, nicht automatisch False
    error: Optional[str] = None
    retrieved_at: str = ""


def get_forecast(symbol: str, current_price: float) -> ForecastResult:
    retrieved_at = datetime.now(timezone.utc).isoformat()

    target = _get("stock/price-target", {"symbol": symbol})
    rec = _get("stock/recommendation", {"symbol": symbol})

    if isinstance(target, dict) and "_error" in target:
        return ForecastResult(error=f"price-target: {target['_error']}", retrieved_at=retrieved_at)
    if isinstance(rec, dict) and "_error" in rec:
        return ForecastResult(error=f"recommendation: {rec['_error']}", retrieved_at=retrieved_at)

    result = ForecastResult(retrieved_at=retrieved_at)

    if target and target.get("targetMean"):
        result.target_average = target["targetMean"]
        if current_price:
            result.target_upside_pct = round(
                (target["targetMean"] / current_price - 1) * 100, 2
            )
        # target_recently_cut braucht einen lokalen Snapshot-Vergleich (siehe rules.yaml,
        # 14-Tage-Fenster) — Finnhub liefert keine Historie, das bleibt UNKNOWN hier.

    if rec and isinstance(rec, list) and len(rec) > 0:
        latest = rec[0]  # neuester Monat zuerst
        result.rating_buy = latest.get("buy", 0) + latest.get("strongBuy", 0)
        result.rating_hold = latest.get("hold", 0)
        result.rating_sell = latest.get("sell", 0) + latest.get("strongSell", 0)

    return result


@dataclass
class NewsResult:
    headlines: list = field(default_factory=list)
    has_negative_keyword: Optional[bool] = None  # None = UNKNOWN bei leerem Ergebnis
    error: Optional[str] = None
    retrieved_at: str = ""


NEGATIVE_KEYWORDS = [
    "miss", "cuts guidance", "downgrade", "investigation", "lawsuit", "recall",
    "halted", "delisting", "bankruptcy", "restatement", "offering", "dilution",
    "resigns", "fraud", "warns",
]


def get_news(symbol: str) -> NewsResult:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    now = datetime.now(timezone.utc)
    frm = (now - timedelta(days=NEWS_WINDOW_DAYS)).strftime("%Y-%m-%d")
    to = now.strftime("%Y-%m-%d")

    raw = _get("company-news", {"symbol": symbol, "from": frm, "to": to})
    if isinstance(raw, dict) and "_error" in raw:
        return NewsResult(error=raw["_error"], retrieved_at=retrieved_at)
    if not raw:
        # Keine News gefunden != "keine negativen News bestätigt"
        return NewsResult(headlines=[], has_negative_keyword=None, retrieved_at=retrieved_at)

    headlines = [item.get("headline", "") for item in raw]
    lowered = " ".join(h.lower() for h in headlines)
    has_negative = any(kw in lowered for kw in NEGATIVE_KEYWORDS)

    return NewsResult(headlines=headlines[:10], has_negative_keyword=has_negative,
                       retrieved_at=retrieved_at)


def collect_symbol(symbol: str, current_price: float) -> dict:
    """Für einen Symbol-Loop: Forecast + News mit Stagger dazwischen."""
    forecast = get_forecast(symbol, current_price)
    time.sleep(STAGGER_SECONDS)
    news = get_news(symbol)
    time.sleep(STAGGER_SECONDS)
    return {"forecast": forecast, "news": news}


if __name__ == "__main__":
    import sys
    import json
    from dataclasses import asdict

    symbols = sys.argv[1:] or ["AAPL"]
    for sym in symbols:
        print(f"\n=== {sym} ===")
        out = collect_symbol(sym, current_price=100.0)  # Platzhalter-Preis für lokalen Test
        print(json.dumps({k: asdict(v) for k, v in out.items()}, indent=2, default=str))
