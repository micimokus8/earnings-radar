#!/usr/bin/env python3
"""Pump-Ledger: Snapshot -> Outcome -> Feature-Statistik.

Der Ablauf, den der User will:
  1. snapshot : aus gespeicherten Reports Kandidaten + Merkmale + Entry-Preis
                nach data/ledger/snapshots.jsonl schreiben (idempotent).
  2. resolve  : pro noch offenem Snapshot die 1D-Kerzen holen (TwelveData),
                Close am Report-Tag (day0) und naechsten Handelstag (day1)
                bestimmen, Return rechnen, PUMP/FLAT/REINFALL klassifizieren,
                nach data/ledger/outcomes.jsonl schreiben.
  3. stats    : die Merkmale der Gewinner vs. Verlierer auszaehlen.

Entry-Preis = 'price_1d' aus dem Report (Intraday-Snapshot ~10:30 ET).
Zwei Returns werden gemessen, weil der Report mitten in der Session laeuft:
  - ret_entry      : Entry-Preis -> Close day1   (realistischer Kaufhorizont)
  - ret_close_day01: Close day0 -> Close day1    (reiner Pump am Folgetag)
PUMP = ret_close_day01 >= 8% ODER ret_entry >= 10%.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPORTS = ROOT / "data" / "reports"
LEDGER = ROOT / "data" / "ledger"
SNAPSHOTS = LEDGER / "snapshots.jsonl"
OUTCOMES = LEDGER / "outcomes.jsonl"

PUMP_THRESHOLD = 8.0   # % ab Close day0 -> day1
ENTRY_THRESHOLD = 10.0  # % ab Report-Entry -> day1


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
    LEDGER.mkdir(parents=True, exist_ok=True)
    existing = set()
    if SNAPSHOTS.exists():
        for line in SNAPSHOTS.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                existing.add((r["report_date"], r["report_type"], r["symbol"]))

    files = sorted(REPORTS.glob("*.json"))
    if args.since:
        files = [f for f in files if f.name[:10] >= args.since]
    added = 0
    with SNAPSHOTS.open("a", encoding="utf-8") as fh:
        for path in files:
            try:
                rep = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"skip {path.name}: {e}", file=sys.stderr)
                continue
            rdate = rep.get("report_date")
            rtype = rep.get("report_type")
            # Vorab-These der LLM-Bewertung (falls vorhanden) laden
            thesis_map = {}
            tf = LEDGER / "theses" / f"{rdate}_{rtype}.json"
            if tf.exists():
                try:
                    thesis_map = json.loads(tf.read_text(encoding="utf-8")).get("theses", {})
                except Exception:
                    thesis_map = {}
            for c in rep.get("candidates", []):
                sym = str(c.get("symbol", "")).split(":")[-1].strip()
                if not sym:
                    continue
                key = (rdate, rtype, sym)
                if key in existing:
                    continue
                score = c.get("score") or {}
                rec = {
                    "report_date": rdate,
                    "report_type": rtype,
                    "symbol": sym,
                    "entry_price": (c.get("values") or {}).get("price_1d"),
                    "label": score.get("label"),
                    "score_pct": score.get("score_pct"),
                    "thesis": thesis_map.get(sym),
                    "features": _features(c),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                existing.add(key)
                added += 1
    print(f"Snapshots neu: {added} (gesamt {len(existing)})")
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
                done.add((r["report_date"], r["symbol"]))

    snaps = [json.loads(l) for l in SNAPSHOTS.read_text().splitlines() if l.strip()]
    # Nur offene, mit Entry-Preis. Pro Symbol gruppieren -> 1 Call/Symbol.
    by_sym: dict[str, list[dict]] = {}
    for s in snaps:
        key = (s["report_date"], s["symbol"])
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

            dates = sorted({c["datetime"][:10] for c in candles})
            close_by_date = {c["datetime"][:10]: c["close"] for c in candles}

            for s in by_sym[sym]:
                rdate = s["report_date"]
                day0 = close_by_date.get(rdate)
                later = [d for d in dates if d > rdate]
                day1 = close_by_date.get(later[0]) if later else None
                entry = s["entry_price"]

                # day1 (= eigentlicher Pump-Tag/Close) fehlt noch, Report ist
                # aber frisch -> NICHT festschreiben, beim naechsten Lauf erneut
                # versuchen. Erst nach 7 Tagen als wirklich unaufloesbar werten.
                if day1 is None:
                    try:
                        from datetime import date as _date, datetime as _dt
                        age = (_date.today() - _dt.strptime(rdate, "%Y-%m-%d").date()).days
                    except Exception:
                        age = 999
                    if age <= 7:
                        continue
                    verdict = "UNRESOLVED"
                else:
                    ret_entry = ((day1 - entry) / entry * 100) if (day1 and entry) else None
                    ret_d01 = ((day1 - day0) / day0 * 100) if (day0 and day1) else None
                    if (ret_d01 is not None and ret_d01 >= PUMP_THRESHOLD) or \
                       (ret_entry is not None and ret_entry >= ENTRY_THRESHOLD):
                        verdict = "PUMP"
                    elif (ret_d01 is not None and ret_d01 <= -5) or (ret_entry is not None and ret_entry <= -5):
                        verdict = "REINFALL"
                    else:
                        verdict = "FLAT"
                ret_entry = ((day1 - entry) / entry * 100) if (day1 and entry) else None
                ret_d01 = ((day1 - day0) / day0 * 100) if (day0 and day1) else None

                rec = {
                    **{k: s[k] for k in ("report_date", "report_type", "symbol",
                                         "entry_price", "label", "score_pct")},
                    "day0_close": day0,
                    "day1_date": later[0] if later else None,
                    "day1_close": day1,
                    "ret_entry": round(ret_entry, 2) if ret_entry is not None else None,
                    "ret_close_day01": round(ret_d01, 2) if ret_d01 is not None else None,
                    "verdict": verdict,
                    "features": s["features"],
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                wrote += 1
                if args.verbose:
                    print(f"  {sym:6} {rdate}: {verdict:9} ret_entry={ret_entry} ret_01={ret_d01}")
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
    recs = [r for r in allrecs if r["verdict"] in ("PUMP", "FLAT", "REINFALL")]
    unres = len(allrecs) - len(recs)
    n = len(recs)
    if n == 0:
        print(f"Noch keine aufgeloesten Outcomes (offen/unaufloesbar: {unres}).")
        return 0
    pumps = sum(1 for r in recs if r["verdict"] == "PUMP")
    print(f"\n== Aufloesbar: {n} | PUMP {pumps} ({pumps/n*100:.0f}%) | "
          f"offen/UNRESOLVED: {unres} ==\n")

    def ret(r):
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
