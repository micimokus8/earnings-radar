#!/usr/bin/env python3
"""Generate the second (LLM) message from the saved report file.

Reads today's deterministic report JSON, runs the LLM interpretation on the
labelled candidates, and prints the evaluation text to stdout (delivered as a
separate Telegram message by a cron job).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

from earnings_monitor.llm_interpretation import interpret_candidates
from earnings_monitor.wiring import load_optional_text


def _labelled(candidates) -> list[dict]:
    return [c for c in candidates if (c.get("score") or {}).get("label")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Second (LLM) earnings message")
    parser.add_argument("--report-type", default="AFTER_CLOSE",
                        choices=["BEFORE_OPEN", "AFTER_CLOSE"])
    parser.add_argument("--report-date", default=None,
                        help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--out-dir", default="data/reports")
    parser.add_argument("--llm-key", default="LLM Key.txt")
    parser.add_argument("--llm-model-file", default="LLM Model.txt")
    parser.add_argument("--llm-model", default="stealth/ox-alpha")
    parser.add_argument("--llm-base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--llm-enabled-file", default="LLM Enabled.txt")
    args = parser.parse_args()

    enabled = True
    flag = load_optional_text(args.llm_enabled_file)
    if flag and flag.strip().upper() in {"OFF", "NO", "AUS", "0", "FALSE"}:
        enabled = False
    if not enabled:
        return 0

    report_date = args.report_date or datetime.now().strftime("%Y-%m-%d")
    out_dir = pathlib.Path(args.out_dir)
    path = out_dir / f"{report_date}_{args.report_type}.json"
    if not path.exists():
        # No deterministic scan ran (e.g. no earnings found) -> stay silent.
        return 0

    report = json.loads(path.read_text(encoding="utf-8"))
    labelled = _labelled(report.get("candidates", []))[:5]
    if not labelled:
        print(f"🤖 LLM-Bewertung {args.report_type.replace('_', ' ')} "
              f"{report_date}: keine auswertbaren Kandidaten (alle unvollständig).")
        return 0

    api_key = load_optional_text(args.llm_key)
    if not api_key:
        print(f"🤖 LLM-Bewertung: kein Key in '{args.llm_key}' - übersprungen.")
        return 0

    model = load_optional_text(args.llm_model_file) or args.llm_model
    result = interpret_candidates(
        labelled, api_key=api_key, base_url=args.llm_base_url, model=model
    )
    deutung = result.get("deutung", {})
    empfehlung = result.get("empfehlung", "")
    if not deutung and not empfehlung:
        print(f"🤖 LLM-Bewertung {args.report_type.replace('_', ' ')} "
              f"{report_date}: Interpretation fehlgeschlagen.")
        return 0

    lines = [
        f"🤖 LLM-Bewertung ({model}) — {args.report_type.replace('_', ' ')} {report_date}",
        "",
    ]
    for c in labelled:
        sym = c.get("symbol")
        txt = deutung.get(sym)
        lines.append(f"• {sym.split(':')[-1]}: {txt}" if txt else f"• {sym.split(':')[-1]}: —")
    if empfehlung:
        lines.append("")
        lines.append("🎯 Meine Empfehlung")
        lines.append(empfehlung)
    print("\n".join(lines).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())