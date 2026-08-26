#!/usr/bin/env python3
"""Sharded earnings scan.

Discover earnings symbols ONCE, then scan them in parallel chunks (each its own
run_scan subprocess) and merge the shard reports into one deterministic report.

This keeps a single cron run inside the 600s scheduler cap while processing every
symbol: the wall-clock cost is the SLOWEST chunk, not the sum of all symbols.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from earnings_monitor.dedup import dedupe_dual_class_symbols
from earnings_monitor.report_builder import merge_reports
from earnings_monitor.telegram_report import render_report

SCRIPT_DIR = Path(__file__).resolve().parent


def _run(args, extra, *, capture=True, timeout=None):
    cmd = [sys.executable, str(SCRIPT_DIR / "run_scan.py"), *extra]
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _discover_symbols(args, timeout) -> list[str]:
    try:
        result = _run(args, [
            "--discover-only",
            "--report-type", args.report_type,
            "--target-date", args.target_date or "",
            "--min-market-cap", str(args.min_market_cap),
            "--exclude-prefixes", args.exclude_prefixes,
            "--max-symbols", str(args.max_symbols),
            "--tvremix-secret", args.tvremix_secret,
        ], timeout=timeout)
    except subprocess.TimeoutExpired:
        sys.stderr.write("[discover] Discovery ueberschritt Budget - Scan abgebrochen.\n")
        return []
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return []
    return result.stdout.split()


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def main() -> int:
    parser = argparse.ArgumentParser(description="Sharded earnings scan (split + merge)")
    parser.add_argument("--report-type", default="BEFORE_OPEN",
                        choices=["BEFORE_OPEN", "AFTER_CLOSE"])
    parser.add_argument("--target-date", default=None)
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--min-market-cap", type=float, default=2_000_000_000)
    parser.add_argument("--exclude-prefixes", default="OTC:")
    parser.add_argument("--max-symbols", type=int, default=24)
    parser.add_argument("--chunk-size", type=int, default=6,
                        help="Symbols per parallel scan chunk (rate-limit safe)")
    parser.add_argument("--per-chunk-deadline", type=float, default=380.0,
                        help="Wall-clock budget per chunk; MUST stay under overall-budget so a slow "
                             "chunk writes its partial shard JSON instead of being killed first")
    parser.add_argument("--overall-budget", type=float, default=580.0,
                        help="Hard total budget for the whole sharded run; chunks past this are killed "
                             "(keeps the cron job safely under the 600s scheduler cap)")
    parser.add_argument("--tvremix-secret", default="tvremix API.txt")
    parser.add_argument("--finnhub-key", default="Finhub Key.txt")
    parser.add_argument("--out-dir", default="data/reports")
    args = parser.parse_args()

    # Discovery counts against the overall budget so a slow discovery alone
    # can never stall the cron job past the scheduler cap.
    budget = args.overall_budget
    t_start = time.monotonic()
    symbols = _discover_symbols(args, timeout=budget)
    discover_elapsed = time.monotonic() - t_start
    budget = max(0.0, budget - discover_elapsed)
    if not symbols:
        print(f"📅 {args.report_type.replace('_', ' ')} — keine Symbole gefunden.")
        return 0

    # --chunks began, timing restarts here: budget is measured from NOW onward
    chunk_t0 = time.monotonic()

    # Dedupe once on the full list so dual-class pairs (HEI/HEI.A) are never
    # split across chunks, which would otherwise survive into the merged report.
    symbols = dedupe_dual_class_symbols(symbols)

    work = Path(tempfile.mkdtemp(prefix="earnings_shard_"))
    shard_paths: list[Path] = []
    procs: list[subprocess.Popen] = []
    for index, chunk in enumerate(_chunks(symbols, args.chunk_size)):
        shard_path = work / f"shard_{index}.json"
        shard_paths.append(shard_path)
        procs.append(_run(args, [
            "--symbols", ",".join(chunk),
            "--report-type", args.report_type,
            "--as-of", args.as_of or "",
            "--out-file", str(shard_path),
            "--deadline-seconds", str(args.per_chunk_deadline),
            "--tvremix-secret", args.tvremix_secret,
            "--finnhub-key", args.finnhub_key,
        ], capture=False))

    # Wait for all chunks, but with the absolute overall budget (discovery
    # time already subtracted) so the whole cron job stays under the 600s
    # scheduler cap; past the budget we kill any still-running chunk and merge
    # whatever finished.
    for proc in procs:
        remaining = budget - (time.monotonic() - chunk_t0)
        if remaining <= 0:
            proc.kill()
        else:
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                proc.kill()
    for proc in procs:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    reports = []
    for shard_path in shard_paths:
        if shard_path.exists():
            try:
                reports.append(json.loads(shard_path.read_text()))
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(f"[merge] shard {shard_path} ungueltig: {exc}\n")
        else:
            sys.stderr.write(f"[merge] shard {shard_path} fehlt (Chunk fehlgeschlagen)\n")

    if not reports:
        print("📅 Scan fehlgeschlagen (keine Shard-Ergebnisse).")
        return 1

    merged = merge_reports(reports, report_type=args.report_type)

    # Detect silently-lost symbols: every discovered symbol (minus those
    # intentionally deduped) must appear in the merged report. If not, flag it
    # loudly instead of pretending the scan was complete.
    reported = {
        c["symbol"] for report in reports for c in report.get("candidates", [])
    }
    removed = set()
    for report in reports:
        removed |= set(report.get("quality", {}).get("removed_duplicate_symbols", []) or [])
    expected = set(symbols) | removed
    lost = sorted(expected - reported)
    merged["quality"]["lost_symbols"] = lost
    if lost:
        merged["quality"]["truncated"] = True
        sys.stderr.write(f"[verlust] {len(lost)} Symbol(e) fehlen im Report: {', '.join(lost)}\n")
        # Sequential rescue pass: each lost symbol gets its own small scan,
        # bounded by (remaining outer budget / number of lost symbols). This
        # guarantees zero lost symbols in the steady state: the expensive
        # mega-cap chunk produced a shard that was killed, but the individual
        # tickers inside it can be rescued cheaply.
        remaining = budget - (time.monotonic() - chunk_t0)
        if remaining >= 35 and lost:
            per_rescue = max(35.0, min(args.per_chunk_deadline, remaining / len(lost)))
            sys.stderr.write(f"[rescue] starte Einzel-Rettung: {len(lost)} Symbol(e), je {per_rescue:.0f}s\n")
            for sym in lost[:]:
                # budget check between symbols
                remaining = budget - (time.monotonic() - chunk_t0)
                if remaining < 30:
                    sys.stderr.write("[rescue] Budget aufgebraucht, Abbruch Rettung\n")
                    break
                per_sym = min(per_rescue, remaining - 6)  # 6s reserve for merge/write
                if per_sym < 28:
                    per_sym = remaining - 6
                if per_sym < 20:
                    break
                rescue_path = work / f"rescue_{sym.replace(':', '_')}.json"
                shard_paths.append(rescue_path)
                rp = _run(args, [
                    "--symbols", sym,
                    "--report-type", args.report_type,
                    "--as-of", args.as_of or "",
                    "--out-file", str(rescue_path),
                    "--deadline-seconds", str(per_sym),
                    "--tvremix-secret", args.tvremix_secret,
                    "--finnhub-key", args.finnhub_key,
                ], capture=False)
                try:
                    rp.wait(timeout=per_sym + 12)
                except subprocess.TimeoutExpired:
                    rp.kill()
                    try:
                        rp.wait(timeout=6)
                    except subprocess.TimeoutExpired:
                        pass
                if rescue_path.exists():
                    try:
                        reports.append(json.loads(rescue_path.read_text()))
                    except Exception as exc:
                        sys.stderr.write(f"[rescue] shard {rescue_path} ungueltig: {exc}\n")
                        continue
                    sys.stderr.write(f"[rescue] {sym} gerettet\n")
                else:
                    sys.stderr.write(f"[rescue] {sym} weiterhin fehlend\n")
            # Re-merge including rescued shards.
            if reports:
                merged = merge_reports(reports, report_type=args.report_type)
                reported2 = {c["symbol"] for r in reports for c in r.get("candidates", [])}
                removed2 = set()
                for r in reports:
                    removed2 |= set(r.get("quality", {}).get("removed_duplicate_symbols", []) or [])
                expected2 = set(symbols) | removed2
                lost2 = sorted(expected2 - reported2)
                merged["quality"]["lost_symbols"] = lost2
                if lost2:
                    merged["quality"]["truncated"] = True
                    sys.stderr.write(f"[verlust-nach-rescue] noch fehlend: {', '.join(lost2)}\n")
                else:
                    # Keep truncated flag if any shard was truncated (partial rescued shard).
                    merged["quality"]["truncated"] = any(
                        bool(r.get("quality", {}).get("truncated")) for r in reports
                    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_id = merged["report_id"].replace(":", "_")
    out_path = out_dir / f"{safe_id}.json"
    out_path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")

    print(render_report(merged))

    quality = merged["quality"]
    sys.stderr.write(f"\n[artifact] {out_path}\n")
    sys.stderr.write(
        f"[quality] candidates={quality['candidate_count']} "
        f"incomplete={quality['incomplete_count']} "
        f"truncated={quality.get('truncated', False)} "
        f"shards={len(reports)}/{len(shard_paths)}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
