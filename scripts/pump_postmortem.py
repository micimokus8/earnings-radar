#!/usr/bin/env python3
"""Pump-Postmortem: nach dem Resolve die Vorab-These mit dem echten Move abgleichen.

Liest outcomes.jsonl (verdict PUMP/FLAT/REINFALL), holt die Vorab-These aus
snapshots.jsonl und laesst das LLM pro Kandidat beurteilen:
  - war die Pump-These bestaetigt oder widerlegt?
  - was war der wahre Zuender / Grund (falls Pump) bzw. warum kein Pump?
  - 1 kompakte Lesson daraus.

Schreibt data/ledger/postmortems.jsonl (idempotent, ein Eintrag je
(report_date, symbol)). Ausserdem --week: aggregiert die Lessons der letzten
7 Tage zu data/ledger/lessons.md, das llm_interpretation.py in den Prompt laedt.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.request
from datetime import date as _date, datetime as _dt, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data" / "ledger"
OUTCOMES = LEDGER / "outcomes.jsonl"
SNAPSHOTS = LEDGER / "snapshots.jsonl"
POSTMORTEMS = LEDGER / "postmortems.jsonl"
LESSONS = LEDGER / "lessons.md"

DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"


def _load_key_model():
    key = (ROOT / "LLM Key.txt").read_text().strip()
    mf = ROOT / "LLM Model.txt"
    model = mf.read_text().strip() if mf.exists() else DEFAULT_MODEL
    return key, model or DEFAULT_MODEL


def _ask(url, api_key, payload, timeout=240):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _snap_map():
    m = {}
    if SNAPSHOTS.exists():
        for line in SNAPSHOTS.read_text().splitlines():
            if line.strip():
                s = json.loads(line)
                m[(s["report_date"], s["symbol"])] = s
    return m


def _done():
    d = set()
    if POSTMORTEMS.exists():
        for line in POSTMORTEMS.read_text().splitlines():
            if line.strip():
                p = json.loads(line)
                d.add((p["report_date"], p["symbol"]))
    return d


def _prompt(batch: list[dict]) -> str:
    blocks = []
    for o in batch:
        f = o.get("features") or {}
        blocks.append(
            f"Symbol: {o['symbol']} | Datum: {o['report_date']} | Verdict: {o['verdict']}\n"
            f"Preis(Hint): {o.get('entry_price')} | Close Tag0: {o.get('day0_close')} | "
            f"Close Tag1: {o.get('day1_close')} | Ret Tag0->1: {o.get('ret_close_day01')}% | "
            f"Ret Entry->1: {o.get('ret_entry')}%\n"
            f"Merkmale: RSI={f.get('rsi')}, Short%={f.get('short_pct')}, DTC={f.get('days_to_cover')}, "
            f"5d%={f.get('change_5d_pct')}, 1d%={f.get('daily_change_pct')}, ADX={f.get('adx')}, "
            f"Abstand52W%={f.get('distance_to_52w_pct')}, P<EMA20={f.get('below_ema20')}\n"
            f"Vorab-These: {o.get('thesis') or 'keine (kein LLM-Text gespeichert)'}"
        )
    return ("Du bist Pump-Postmortem-Analyst. Fuer jede Aktie unten liegt die Einschaetzung "
            "VOR dem Move (Vorab-These) und das tatsaechliche Ergebnis (Earnings-Reaktion "
            "Tag0->Tag1) vor.\n\n"
            "Bewerte AUSSCHLIESSLICH die Vorab-These, nicht das Ergebnis an sich:\n"
            "- BESTAETIGT = die Vorab-These traf ein (hohes Pump-Potenzial vorhergesagt UND gepumpt, "
            "oder niedriges Potenzial vorhergesagt UND nicht gepumpt).\n"
            "- WIDERLEGT = die Vorab-These traf NICHT ein (hohes Potenzial vorhergesagt, aber kein "
            "Pump; oder niedriges Potenzial vorhergesagt, aber starker Pump).\n"
            "- KEINE_THESE = es liegt keine Vorab-Einschaetzung vor.\n\n"
            "Dann: (2) Was war der wahre Zuender / Grund? (3) Eine kurze, allgemein nutzbare "
            "Lesson fuer kuenftige Pump-Erkennung. Erfinde keine Zahlen. Deutsch, kompakt.\n\n"
            "Verwende EXAKT pro Symbol dieses Format (eine Zeile):\n"
            "SYMBOL | BESTAETIGT/WIDERLEGT/KEINE_THESE | Zuender: ... | Lesson: ...\n\n"
            + "\n\n".join(blocks))


def cmd_run(args) -> int:
    if not OUTCOMES.exists():
        print("Keine outcomes.")
        return 0
    snaps = _snap_map()
    done = _done()
    outs = [json.loads(l) for l in OUTCOMES.read_text().splitlines() if l.strip()]
    todo = []
    for o in outs:
        if o["verdict"] not in ("PUMP", "FLAT", "REINFALL"):
            continue
        key = (o["report_date"], o["symbol"])
        if key in done:
            continue
        s = snaps.get(key, {})
        o = {**o, "thesis": s.get("thesis")}
        todo.append(o)
    if not todo:
        print("Keine neuen Outcomes fuer Postmortem.")
        return 0
    if args.limit:
        todo = todo[: args.limit]

    key, model = _load_key_model()
    thinking_budget = 16000
    batch_size = 12  # ein Call pro ~12 Kandidaten, haelt Output zusammen
    # Budget: stoppt kontrolliert, damit resolve+postmortem zusammen unter die
    # 600s Cron-Grenze fallen. Naechster Lauf macht mit den restlichen weiter.
    wall_budget = float(args.budget or 240.0)
    t_start = time.monotonic()
    wrote = 0
    with POSTMORTEMS.open("a", encoding="utf-8") as fh:
        for i in range(0, len(todo), batch_size):
            if (time.monotonic() - t_start) >= wall_budget:
                print(f"[budget] {wall_budget:.0f}s aufgebraucht — restliche "
                      f"Postmortems beim naechsten Lauf.", file=sys.stderr)
                break
            batch = todo[i:i + batch_size]
            payload = {
                "model": model,
                "temperature": 0.3,
                "max_tokens": thinking_budget,
                "messages": [
                    {"role": "system", "content": "Du bist ein nuechterner Trading-Postmortem-Analyst."},
                    {"role": "user", "content": _prompt(batch)},
                ],
            }
            try:
                resp = _ask("https://openrouter.ai/api/v1/chat/completions", key, payload)
                raw = (resp["choices"][0].get("message", {}).get("content") or "").strip()
            except Exception as e:
                print(f"LLM-Fehler: {e}", file=sys.stderr)
                continue
            if not raw:
                fin = resp["choices"][0].get("finish_reason")
                print(f"Leere Antwort (finish_reason={fin})", file=sys.stderr)
                continue
            # Antwort zeilenweise auf Symbole mappen
            parsed = {}
            for line in raw.splitlines():
                if "|" not in line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 3:
                    continue
                sym = parts[0].lstrip('*•- ').split(":")[-1].strip().upper()
                parsed[sym] = {
                    "urteil": parts[1].replace("**", "").strip(),
                    "zuender": parts[2].removeprefix("Zuender:").strip(),
                    "lesson": (parts[3].removeprefix("Lesson:").strip() if len(parts) > 3 else ""),
                    "raw": line.strip(),
                }
            for o in batch:
                pm = parsed.get(o["symbol"].upper()) or {"urteil": "?", "zuender": "", "lesson": "", "raw": ""}
                # Ohne Vorab-These deterministisch KEINE_THESE (LLM kann das nicht bewerten)
                if not o.get("thesis"):
                    pm["urteil"] = "KEINE_THESE"
                fh.write(json.dumps({
                    "report_date": o["report_date"],
                    "symbol": o["symbol"],
                    "verdict": o["verdict"],
                    "ret_close_day01": o.get("ret_close_day01"),
                    "thesis": o.get("thesis"),
                    **pm,
                }, ensure_ascii=False) + "\n")
                wrote += 1
            fh.flush()
    print(f"Postmortems neu: {wrote} (Modell {model})")
    return 0


def cmd_week(args) -> int:
    """Aggregiert die Lessons der letzten 7 Tage zu einem kompakten Prompt-Block."""
    if not POSTMORTEMS.exists():
        print("Keine postmortems.")
        return 0
    recs = [json.loads(l) for l in POSTMORTEMS.read_text().splitlines() if l.strip()]
    cutoff = (_date.today() - timedelta(days=args.days)).isoformat()
    recent = [r for r in recs if r["report_date"] >= cutoff]
    if not recent:
        # Fallback: alle, falls noch keine 7 Tage Historie
        recent = recs
    # Nur echte Urteile (mit These) eingehen lassen, KEINE_THESE ist kein Lernsignal.
    judged = [r for r in recent if r.get("urteil") in ("BESTAETIGT", "WIDERLEGT")]
    pumps = [r for r in judged if r["verdict"] == "PUMP" and r["urteil"] == "BESTAETIGT"]
    flops = [r for r in judged if r["urteil"] == "WIDERLEGT"]
    lines = [f"# Earnings-Pump Lessons (Stand {_date.today().isoformat()})", ""]
    lines.append(f"Ausgewertet: {len(recent)} Kandidaten, {len(judged)} mit These beurteilt "
                 f"({len(pumps)} bestätigte Pumps, {len(flops)} widerlegte Thesen).")
    lines.append("")
    lines.append("## Was bei Pump-Erkennung funktioniert hat (bestätigt)")
    for r in pumps[:15]:
        if r.get("lesson"):
            lines.append(f"- {r['symbol']} ({r['ret_close_day01']}%): {r['lesson']}")
    lines.append("")
    lines.append("## Was getaeuscht hat (widerlegt)")
    for r in flops[:15]:
        if r.get("lesson"):
            lines.append(f"- {r['symbol']} ({r['ret_close_day01']}%): {r['lesson']}")
    LESSONS.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(f"lessons.md geschrieben: {len(recent)} ausgewertet, {len(judged)} beurteilt, "
          f"{len(pumps)} bestätigt, {len(flops)} widerlegt")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pump-Postmortem")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--budget", type=float, default=240.0,
                   help="Max Wand-Zeit (s) je Lauf; stoppt kontrolliert, naechster Lauf macht weiter")
    r.set_defaults(fn=cmd_run)
    w = sub.add_parser("week"); w.add_argument("--days", type=int, default=7); w.set_defaults(fn=cmd_week)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
