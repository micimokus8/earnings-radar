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
from pathlib import Path

from earnings_monitor.dedup import dedupe_dual_class_symbols
from earnings_monitor.report_builder import merge_reports
from earnings_monitor.telegram_report import render_report

SCRIPT_DIR = Path(__file__).resolve().parent


def _run(args, extra, *, capture=True):
    cmd = [sys.executable, str(SCRIPT_DIR / "run_scan.py"), *extra]
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True)
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _discover_symbols(args) -> list[str]:
    result = _run(args, [
        "--discover-only",
        "--report-type", args.report_type,
        "--target-date", args.target_date or "",
        "--min-market-cap", str(args.min_market_cap),
        "--exclude-prefixes", args.exclude_prefixes,
        "--max-symbols", str(args.max_symbols),
        "--tvremix-secret", args.tvremix_secret,
    ])
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
    parser.add_argument("--per-chunk-deadline", type=float, default=560.0,
                        help="Wall-clock budget per chunk (cron-safe margin)")
    parser.add_argument("--tvremix-secret", default="tvremix API.txt")
    parser.add_argument("--finnhub-key", default="Finhub Key.txt")
    parser.add_argument("--out-dir", default="data/reports")
    args = parser.parse_args()

    symbols = _discover_symbols(args)
    if not symbols:
        print(f"📅 {args.report_type.replace('_', ' ')} — keine Symbole gefunden.")
        return 0

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

    for proc in procs:
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
