"""Midday pre-selection versus the check just before the close.

The live price is appended as a provisional close so RSI, stochastic and the
distance to resistance see the move. It is not stored as a finished daily bar.
A name that already ran, or that fell sharply, since the pre-selection is
blocked and is not recommended.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from earnings_monitor.indicators import high_52w, next_resistance, stochastic_k
from earnings_monitor.paths import ledger_dir, repo_root
from earnings_monitor.scoring import score_candidate

_ET = ZoneInfo("America/New_York")
_BERLIN = ZoneInfo("Europe/Berlin")


def load_thresholds(path: Path | None = None) -> tuple[float, float]:
    """Return (ran_pct, drop_pct). File lines: ran_pct=5 and drop_pct=5."""
    ran, drop = 5.0, 5.0
    file = path or (repo_root() / "Freshness.txt")
    try:
        text = file.read_text(encoding="utf-8")
    except OSError:
        return ran, drop
    for line in text.splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        try:
            number = float(value)
        except ValueError:
            continue
        if key == "ran_pct":
            ran = number
        elif key == "drop_pct":
            drop = number
    return ran, drop


def price_move_pct(old, new) -> float | None:
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
        return None
    if old <= 0 or new <= 0:
        return None
    return (float(new) / float(old) - 1.0) * 100.0


def drift_reason(move, ran_pct: float, drop_pct: float) -> str | None:
    if move is None:
        return None
    if move >= ran_pct:
        return "SCHON_GELAUFEN"
    if move <= -abs(drop_pct):
        return "SCHARFER_RUECKGANG"
    return None


def _as_bar(row: dict) -> dict | None:
    try:
        high = float(row.get("h", row.get("high")))
        low = float(row.get("l", row.get("low")))
        close = float(row.get("c", row.get("close")))
    except (TypeError, ValueError):
        return None
    if min(high, low, close) <= 0:
        return None
    return {"h": high, "l": low, "c": close}


def recompute_with_live_price(values: dict, daily_bars, live_price: float) -> dict:
    """Copy values and fold *live_price* into RSI, stochastic and room.

    The provisional bar is only for this recalculation.
    """
    updated = dict(values)
    updated["price"] = float(live_price)
    bars = [bar for bar in (_as_bar(row) for row in (daily_bars or [])) if bar]
    if len(bars) < 20:
        return updated
    last = bars[-1]
    bars.append({
        "h": max(last["h"], float(live_price)),
        "l": min(last["l"], float(live_price)),
        "c": float(live_price),
    })
    from earnings_monitor.alternative_sources import _rsi

    closes = [bar["c"] for bar in bars]
    updated["rsi_1d"] = _rsi(closes)
    updated["stoch_k_1d"] = stochastic_k(bars)
    updated["high_52w"] = high_52w(bars)
    updated["resistance_price"] = next_resistance(bars)
    return updated


def format_priced_at(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_ET)
    ny = moment.astimezone(_ET)
    berlin = moment.astimezone(_BERLIN)
    return (
        f"Datenstand {ny:%d.%m.%Y %H:%M} New York"
        f" · {berlin:%d.%m.%Y %H:%M} Berlin"
    )


def _path(report_date: str, report_type: str) -> Path:
    return ledger_dir() / "preselect" / f"{report_date}_{report_type}.json"


def _bare(symbol: str) -> str:
    return str(symbol).split(":")[-1].strip().upper()


def save_preselect(report: dict, *, priced_at: str) -> Path:
    prices = {}
    for candidate in report.get("candidates") or []:
        symbol = _bare(candidate.get("symbol", ""))
        values = candidate.get("values") or {}
        price = values.get("price") or values.get("price_1d")
        if symbol and isinstance(price, (int, float)) and price > 0:
            prices[symbol] = float(price)
    path = _path(str(report.get("report_date")), str(report.get("report_type")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "report_date": report.get("report_date"),
        "report_type": report.get("report_type"),
        "priced_at": priced_at,
        "prices": prices,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_preselect(report_date: str, report_type: str) -> dict:
    path = _path(report_date, report_type)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    prices = payload.get("prices") if isinstance(payload, dict) else None
    return prices if isinstance(prices, dict) else {}


def apply_freshness(candidate: dict, pre_price, ran_pct: float, drop_pct: float) -> dict:
    """Rescore with the live quote and block a large move since pre-selection."""
    values = dict(candidate.get("values") or {})
    live = values.get("price") or values.get("price_1d")
    bars = ((candidate.get("sources") or {}).get("technicals") or {}).get("daily_bars") or []
    if isinstance(live, (int, float)) and live > 0:
        values = recompute_with_live_price(values, bars, float(live))
    move = price_move_pct(pre_price, live if isinstance(live, (int, float)) else None)
    score = score_candidate(values)
    reason = drift_reason(move, ran_pct, drop_pct)
    if reason:
        prior = score.get("skip_reason")
        score["skip_reason"] = reason if not prior else f"{prior}+{reason}"
        score["label"] = f"SKIP ({score['skip_reason']})"
        score["blocked"] = True
    updated = dict(candidate)
    updated["values"] = values
    updated["score"] = score
    updated["drift_pct"] = None if move is None else round(move, 2)
    updated["preselect_price"] = pre_price
    return updated


__all__ = [
    "load_thresholds",
    "price_move_pct",
    "drift_reason",
    "recompute_with_live_price",
    "format_priced_at",
    "save_preselect",
    "load_preselect",
    "apply_freshness",
]
