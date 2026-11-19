#!/usr/bin/env python3
"""Pump-Ledger: Snapshot -> Outcome -> Feature-Statistik.

1. snapshot : jedes gesendete Signal nach data/ledger/snapshots.jsonl
2. resolve  : Sitzung korrekt auswerten
   AFTER_CLOSE: Schluss Meldetag -> Open und Close des nächsten Handelstags
   BEFORE_OPEN: Schluss des Vortags -> Open und Close des Meldetags
   Einstieg = Kurs der Schlusskontrolle. PUMP >= +10 %, PUMP5 >= +5 %, LOSS <= -5 %.
3. stats    : Trefferquote je Label und Sitzung.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from earnings_monitor.paths import ledger_dir, reports_dir  # noqa: E402
from earnings_monitor.signal_log import record_report  # noqa: E402

REPORTS = reports_dir()
LEDGER = ledger_dir()
SNAPSHOTS = LEDGER / "snapshots.jsonl"
OUTCOMES = LEDGER / "outcomes.jsonl"


# ---------------------------------------------------------------- snapshot
def _features(c: dict) -> dict:
    v = c.get("values", {})
    price = v.get("price_1d")
    ema20 = v.get("ema20_1d")
    return {
        "rsi": v.get("rsi_1d"),
        "adx": v.get("adx_1d"),
        "short_pct": v.get("short_pct_outstanding"),
        "days_to_cover": v.get("days_to_cover"),
        "change_5d_pct": v.get("change_5d_pct"),
        "daily_change_pct": v.get("daily_change_pct"),
        "distance_to_52w_pct": v.get("distance_to_52w_pct"),
        "market_cap": v.get("market_cap"),
        "target_upside_pct": v.get("target_upside_pct"),
        "eps_estimate": v.get("eps_estimate"),
        "analyst_rating": v.get("analyst_rating"),
        "below_ema20": (price is not None and ema20 is not None and price < ema20),
    }


def cmd_snapshot(args) -> int:
    files = sorted(REPORTS.glob("*.json"))
    if args.since:
        files = [f for f in files if f.name[:10] >= args.since]
    added = 0
    for path in files:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"skip {path.name}: {exc}", file=sys.stderr)
            continue
        added += record_report(report)
    print(f"Snapshots neu: {added}")
    return 0


# ---------------------------------------------------------------- resolve
def _close_for(candles: list[dict], date: str):
    for c in candles:
        if c["datetime"][:10] == date:
            return c["close"]
    return None


# Symbols reported within this window keep freshness priority (newest first).
# Everything older is a backlog and is drained OLDEST-first — otherwise every
# run spends its whole wall-clock budget on the freshest symbols and the
# weeks-old tail is never reached (observed: 196 stuck snapshots).
FRESH_DAYS = 5


def _age_days(by_sym: dict, sym: str, today=None) -> int:
    """Days since the symbol's NEWEST pending report date (9999 if unparsable)."""
    from datetime import date
    today = today or date.today()
    try:
        newest = max((x["report_date"] for x in by_sym[sym]), default="")
        return (today - date.fromisoformat(newest)).days
    except Exception:
        return 9999


def _resolve_order(by_sym: dict, today=None) -> list[str]:
    """Order symbols for resolution: fresh (newest first), then backlog (oldest first).

    Pure newest-first starved the tail: the daily budget was always consumed by
    the newest symbols, so old snapshots never got a slot. The backlog is sorted
    ascending so it drains deterministically instead of waiting forever.
    """
    from datetime import date
    today = today or date.today()

    def newest(sym):
        return max((x["report_date"] for x in by_sym[sym]), default="")

    fresh = [s for s in by_sym if _age_days(by_sym, s, today) <= FRESH_DAYS]
    backlog = [s for s in by_sym if _age_days(by_sym, s, today) > FRESH_DAYS]
    fresh.sort(key=newest, reverse=True)   # newest fresh first
    backlog.sort(key=newest)               # oldest backlog first
    return fresh + backlog


def cmd_resolve(args) -> int:
    try:
        from earnings_monitor.twelvedata_source import get_ohlcv
    except Exception as e:
        print(f"TwelveData-Import fehlgeschlagen: {e}", file=sys.stderr)
        return 1

    done = set()
    if OUTCOMES.exists():
        for line in OUTCOMES.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["report_date"], r.get("report_type"), r["symbol"]))

    snaps = [json.loads(l) for l in SNAPSHOTS.read_text().splitlines() if l.strip()]
    # Nur offene, mit Entry-Preis. Pro Symbol gruppieren -> 1 Call/Symbol.
    by_sym: dict[str, list[dict]] = {}
    for s in snaps:
        key = (s["report_date"], s.get("report_type"), s["symbol"])
        if key in done or not s.get("entry_price"):
            continue
        by_sym.setdefault(s["symbol"], []).append(s)
    if not by_sym:
        print("Nichts zu resolven.")
        return 0

    # Reihenfolge: frische Symbole zuerst (neueste zuerst), danach der alte
    # Backlog AELTESTE zuerst (_resolve_order) — so kann das Tagesbudget den
    # Schwanz nicht dauerhaft verdraengen. Siehe _resolve_order.
    syms = _resolve_order(by_sym)
    if getattr(args, "skip_fresh", False):
        # Catch-up mode: only the old backlog. Fresh symbols are resolved by the
        # nightly run AFTER the US close — here the newest "close" would still be
        # an unfinished intraday bar.
        syms = [s for s in syms if _age_days(by_sym, s) > FRESH_DAYS]
    if args.limit:
        syms = syms[: args.limit]

    budget = float(args.budget or 0.0)
    t_start = time.monotonic()

    PRICE_CACHE = LEDGER / "prices"
    PRICE_CACHE.mkdir(parents=True, exist_ok=True)
    LEDGER.mkdir(parents=True, exist_ok=True)
    wrote = 0
    with OUTCOMES.open("a", encoding="utf-8") as fh:
        for i, sym in enumerate(syms):
            if budget > 0 and (time.monotonic() - t_start) >= budget:
                print(f"[budget] {budget:.0f}s aufgebraucht nach {wrote} Outcomes — "
                      f"naechste Symbole beim naechsten Lauf (Cache bleibt erhalten).",
                      file=sys.stderr)
                break
            cache_f = PRICE_CACHE / f"{sym}.json"
            candles = None
            # Gültigkeit des Caches: er muss bis mindestens einen Handelstag
            # NACH dem fruehesten Report-Datum dieses Symbols reichen, sonst
            # fehlt der fuer day1 noetige Close und wir muessen frisch holen.
            need_through = max((s["report_date"] for s in by_sym[sym]), default="")
            if cache_f.exists():
                try:
                    _c = json.loads(cache_f.read_text())
                    _last = sorted({c["datetime"][:10] for c in _c})[-1]
                    if _last > need_through:
                        candles = _c
                except Exception:
                    candles = None
            if candles is None:
                ohlcv = get_ohlcv(sym, interval="1day", outputsize=400)
                if ohlcv.error or not ohlcv.candles:
                    print(f"  {sym}: FEHLER {ohlcv.error}", file=sys.stderr)
                    if i < len(syms) - 1:
                        time.sleep(8)
                    continue
                candles = ohlcv.candles
                cache_f.write_text(json.dumps(candles))
                if i < len(syms) - 1:
                    time.sleep(8)

            bars = [
                {"date": c["datetime"][:10], "open": c.get("open"), "close": c.get("close")}
                for c in candles
            ]
            from earnings_monitor.outcomes import session_returns

            for s in by_sym[sym]:
                rdate = s["report_date"]
                measured = session_returns(
                    report_type=s.get("report_type") or "AFTER_CLOSE",
                    report_date=rdate,
                    bars=bars,
                    entry_price=s.get("entry_price"),
                )
                if measured.get("status") != "PASS":
                    try:
                        from datetime import date as _date, datetime as _dt
                        age = (_date.today() - _dt.strptime(rdate, "%Y-%m-%d").date()).days
                    except Exception:
                        age = 999
                    if age <= 7:
                        continue
                    measured = {**measured, "verdict": "UNRESOLVED"}
                ret_close = measured.get("ret_session_close")
                rec = {
                    **{k: s[k] for k in ("report_date", "report_type", "symbol",
                                         "entry_price", "label", "score_pct") if k in s},
                    "session_date": measured.get("session_date"),
                    "exit_date": measured.get("exit_date"),
                    "base_close": measured.get("base_close"),
                    "ret_session_open": measured.get("ret_session_open"),
                    "ret_session_close": ret_close,
                    "ret_official_close": measured.get("ret_official_close"),
                    # Alias: Schluss-Return ab dem Kurs der Schlusskontrolle.
                    "ret_close_day01": ret_close,
                    "ret_entry": ret_close,
                    "verdict": measured.get("verdict") or "UNRESOLVED",
                    "features": s.get("features"),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                wrote += 1
                if args.verbose:
                    print(f"  {sym:6} {rdate}: {rec['verdict']:9} "
                          f"close={ret_close} open={measured.get('ret_session_open')}")
            fh.flush()
    print(f"Outcomes neu: {wrote} (Symbole verarbeitet: {len(syms)})")
    return 0


# ---------------------------------------------------------------- stats
def _bucket(rec) -> str:
    f = rec.get("features") or {}
    rsi = f.get("rsi")
    five = f.get("change_5d_pct") or 0
    short = f.get("short_pct")
    tags = []
    if rsi is not None:
        tags.append("RSI<30" if rsi < 30 else "RSI30-50" if rsi < 50 else "RSI>50")
    tags.append("5d+" if five >= 3 else "5d-")
    if short is not None:
        tags.append("Short>10" if short > 10 else "Short<=10")
    return " ".join(tags)


def cmd_stats(args) -> int:
    if not OUTCOMES.exists():
        print("Keine outcomes.")
        return 0
    allrecs = [json.loads(l) for l in OUTCOMES.read_text().splitlines() if l.strip()]
    recs = [r for r in allrecs if r["verdict"] in ("PUMP", "PUMP5", "FLAT", "LOSS", "REINFALL")]
    unres = len(allrecs) - len(recs)
    n = len(recs)
    if n == 0:
        print(f"Noch keine aufgeloesten Outcomes (offen/unaufloesbar: {unres}).")
        return 0
    pumps = sum(1 for r in recs if r["verdict"] == "PUMP")
    print(f"\n== Aufloesbar: {n} | PUMP {pumps} ({pumps/n*100:.0f}%) | "
          f"offen/UNRESOLVED: {unres} ==\n")

    def ret(r):
        v = r.get("ret_session_close")
        if v is None:
            v = r.get("ret_close_day01")
        return v if v is not None else (r.get("ret_entry") or 0)

    def stats_for(selector, min_n=1):
        from collections import defaultdict
        agg = defaultdict(lambda: [0, 0, 0.0])
        for r in recs:
            for k in selector(r):
                agg[k][0] += 1
                agg[k][1] += 1 if r["verdict"] == "PUMP" else 0
                agg[k][2] += ret(r)
        return [(k, *v) for k, v in agg.items() if v[0] >= min_n]

    MIN = max(1, n // 20)  # Buckets unter 5% der Stichprobe ausblenden
    print(f"## Einzelmerkmale (min n={MIN})\n")
    print(f"{'Merkmal':<26} {'n':>3} {'PUMP':>5} {'Quote':>6} {'avgRet':>8}")
    for k, tot, p, sr in sorted(stats_for(lambda r: _bucket(r).split(), MIN),
                                key=lambda x: -x[1])[:40]:
        print(f"{k:<26} {tot:>3} {p:>5} {p/tot*100:>5.0f}% {sr/tot:>7.1f}%")

    print(f"\n## Score-Label\n")
    for k, tot, p, sr in sorted(stats_for(lambda r: [str(r.get('label'))], MIN),
                                key=lambda x: -x[1]):
        print(f"{k:<26} {tot:>3} {p:>5} {p/tot*100:>5.0f}% {sr/tot:>7.1f}%")

    print(f"\n## Top PUMPs\n")
    for r in sorted([r for r in recs if r["verdict"] == "PUMP"],
                    key=lambda x: -ret(x))[:15]:
        print(f"  {r['report_date']} {r['symbol']:6} {_bucket(r):24} "
              f"ret_01={r.get('ret_close_day01')}% ret_entry={r.get('ret_entry')}%")
    print(f"\n## Reinfaelle\n")
    for r in sorted([r for r in recs if r["verdict"] == "REINFALL"],
                    key=lambda x: ret(x))[:10]:
        print(f"  {r['report_date']} {r['symbol']:6} {_bucket(r):24} "
              f"ret_01={r.get('ret_close_day01')}% ret_entry={r.get('ret_entry')}%")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pump-Ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot"); s.add_argument("--since", default=None); s.set_defaults(fn=cmd_snapshot)
    r = sub.add_parser("resolve")
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--budget", type=float, default=500.0,
                   help="Max Wand-Zeit (s) je Lauf; stoppt kontrolliert, naechster Lauf macht weiter")
    r.add_argument("--verbose", action="store_true")
    r.add_argument("--skip-fresh", dest="skip_fresh", action="store_true",
                   help="nur den alten Backlog abarbeiten (Catch-up; frische Symbole "
                        "bleiben dem naechtlichen Lauf nach US-Close vorbehalten)")
    r.set_defaults(fn=cmd_resolve)
    st = sub.add_parser("stats"); st.set_defaults(fn=cmd_stats)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
