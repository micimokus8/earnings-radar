#!/usr/bin/env python3
"""Full scan: pipeline -> report -> rendered Telegram text (dry-run)."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from earnings_monitor.llm_interpretation import interpret_candidates
from earnings_monitor.run_report import run_report
from earnings_monitor.telegram_report import render_report
from earnings_monitor.wiring import build_default_pipeline, load_optional_text


def _ny_today() -> str:
    now_ny = datetime.now(ZoneInfo("America/New_York"))
    return now_ny.strftime("%Y-%m-%d")


def _discover(args) -> list[str]:
    """Discover earnings symbols once (screener, NY date) and return the list."""
    from earnings_monitor.wiring import ScreenerDiscoveryClient, build_tvremix_session
    target_date = args.target_date or _ny_today()
    exclude = tuple(p.strip() for p in args.exclude_prefixes.split(",") if p.strip())
    discovery = ScreenerDiscoveryClient(
        build_tvremix_session(secret_path=args.tvremix_secret),
        exclude_prefixes=exclude,
        min_market_cap=args.min_market_cap,
    )
    return discovery.get(target_date)[: max(args.max_symbols, 0)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Earnings monitor scan")
    parser.add_argument("--symbols", default=None,
                        help="Comma-separated TVRemix-style symbols")
    parser.add_argument("--auto-discover", action="store_true",
                        help="Discover earnings symbols via screener (NY date)")
    parser.add_argument("--discover-only", action="store_true",
                        help="Discover earnings symbols and print them (space-separated), then exit")
    parser.add_argument("--target-date", default=None,
                        help="Override discovery date YYYY-MM-DD (default: NY today)")
    parser.add_argument("--report-type", default="BEFORE_OPEN",
                        choices=["BEFORE_OPEN", "AFTER_CLOSE"])
    parser.add_argument("--report-date", default=None,
                        help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--as-of", default=None,
                        help="ISO timestamp (default: now UTC)")
    parser.add_argument("--tvremix-secret", default="tvremix API.txt")
    parser.add_argument("--finnhub-key", default="Finhub Key.txt")
    parser.add_argument("--sec-user-agent", default=None,
                        help="Optional file with SEC User-Agent string")
    parser.add_argument("--interpret", action="store_true",
                        help="Append LLM interpretation section")
    parser.add_argument("--llm-key", default="LLM Key.txt",
                        help="Key file (OpenRouter key)")
    parser.add_argument("--llm-model-file", default="LLM Model.txt",
                        help="File holding the model slug (swap without code changes)")
    parser.add_argument("--llm-model", default="stealth/ox-alpha",
                        help="Fallback model if model file is missing/empty")
    parser.add_argument("--llm-base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--llm-enabled-file", default="LLM Enabled.txt",
                        help="File with ON/OFF to toggle LLM without code edits")
    parser.add_argument("--max-chars", type=int, default=4096,
                        help="Hard cap on rendered message length")
    parser.add_argument("--max-symbols", type=int, default=24,
                        help="Enrichment cap, size-neutral order (rate-limit safe)")
    parser.add_argument("--throttle", type=float, default=0.25,
                        help="Seconds between per-source enrichment calls (rate-limit safety)")
    parser.add_argument("--deadline-seconds", type=float, default=540.0,
                        help="Hard wall-clock budget; scan stops early past it (cron-safe)")
    parser.add_argument("--min-market-cap", type=float, default=None,
                        help="Discovery universe: min market cap (USD)")
    parser.add_argument("--exclude-prefixes", default="",
                        help="Comma-separated symbol prefixes to drop (e.g. 'OTC:')")
    parser.add_argument("--out-dir", default="data/reports")
    parser.add_argument("--out-file", default=None,
                        help="Write report JSON to this exact path instead of auto-named (sharding)")
    args = parser.parse_args()

    if args.discover_only:
        symbols = _discover(args)
        if not symbols:
            print(f"📅 {args.report_type.replace('_', ' ')} — "
                  f"{(args.target_date or _ny_today())}: keine Symbole gefunden.")
        else:
            print(" ".join(symbols))
        return 0

    report_date = args.report_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    as_of = args.as_of or datetime.now(timezone.utc).isoformat()
    deadline = (
        time.monotonic() + args.deadline_seconds
        if args.deadline_seconds and args.deadline_seconds > 0 else None
    )

    pipeline = build_default_pipeline(
        tvremix_secret_path=args.tvremix_secret,
        finnhub_key_path=args.finnhub_key,
        sec_user_agent_path=args.sec_user_agent,
        throttle_seconds=args.throttle,
    )

    if args.auto_discover:
        symbols = _discover(args)
        if not symbols:
            print(
                f"📅 {args.report_type.replace('_', ' ')} — {(args.target_date or _ny_today())}: "
                "Keine Earnings-Daten gefunden (Filter/Heute ohne Reporter). "
                "Nichts zu ermitteln."
            )
            return 0

    else:
        symbols = [s.strip() for s in (args.symbols or "").split(",") if s.strip()]
        if not symbols:
            parser.error("either --symbols or --auto-discover is required")

    report = run_report(
        pipeline,
        symbols=symbols,
        report_type=args.report_type,
        report_date=report_date,
        as_of=as_of,
        deadline=deadline,
    )

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.out_file:
        out_path = pathlib.Path(args.out_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        safe_id = report["report_id"].replace(":", "_")
        out_path = out_dir / f"{safe_id}.json"
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    # ---- optional LLM interpretation
    deutung = {}
    empfehlung = ""
    llm_enabled = True
    flag = load_optional_text(args.llm_enabled_file)
    if flag and flag.strip().upper() in {"OFF", "NO", "AUS", "0", "FALSE"}:
        llm_enabled = False

    if args.interpret and llm_enabled:
        api_key = load_optional_text(args.llm_key)
        if not api_key:
            print(f"[LLM] AUS - kein Key in '{args.llm_key}' (nur deterministisch)", file=sys.stderr)
        else:
            model = load_optional_text(args.llm_model_file) or args.llm_model
            labelled = [c for c in report["candidates"] if (c.get("score") or {}).get("label")]
            if not labelled:
                print("\n[LLM] keine bewertbaren Kandidaten - Deterministik pur", file=sys.stderr)
            else:
                llm_result = interpret_candidates(
                    labelled[:5], api_key=api_key, base_url=args.llm_base_url,
                    model=model,
                )
                deutung = llm_result.get("deutung", {})
                empfehlung = llm_result.get("empfehlung", "")
                if not deutung and not empfehlung:
                    print("\n[LLM] Interpretation fehlgeschlagen - nur deterministisch", file=sys.stderr)
    elif args.interpret and not llm_enabled:
        print("\n[LLM] deaktiviert (LLM Enabled.txt = OFF) - nur deterministisch", file=sys.stderr)

    print(render_report(
        report,
        deutung=deutung,
        empfehlung=empfehlung,
        max_chars=args.max_chars,
    ))

    quality = report["quality"]
    print(f"\n[artifact] {out_path}", file=sys.stderr)
    print(f"[quality] candidates={quality['candidate_count']} "
          f"incomplete={quality['incomplete_count']} "
          f"truncated={quality.get('truncated', False)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

      
