#!/usr/bin/env python3
"""Sharded earnings scan.

Discover earnings symbols ONCE, then scan them in parallel chunks (each its own
run_scan subprocess) and merge the shard reports into one deterministic report.

Each chunk runs for its own per-chunk-deadline independent of other chunks.
The scheduler's 600s cron timeout is the absolute safety net — no shrinking
outer budget needed.

Parallel rescue pass: any symbols not covered by the main chunks are
rescued in a single parallel batch with their own deadline.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from earnings_monitor.dedup import dedupe_dual_class_symbols
from earnings_monitor.report_builder import merge_reports
from earnings_monitor.telegram_report import render_report

SPAWN_STAGGER = 8.0  # seconds between launching each parallel chunk
SCRIPT_DIR = Path(__file__).resolve().parent


def _run(args, extra, *, capture=True, timeout=None):
    cmd = [sys.executable, str(SCRIPT_DIR / "run_scan.py"), *extra]
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", str(SCRIPT_DIR.parent))
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    # Forward subprocess stderr to parent stderr so we can see crash traces
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, env=env)


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


def _wait_all(procs, deadline: float):
    """Wait for all processes. Each gets up to ``deadline`` wall-clock seconds
    starting from NOW. Processes already finished return instantly."""
    for p in procs:
        try:
            p.wait(timeout=max(1.0, deadline))
        except subprocess.TimeoutExpired:
            p.kill()
    # Guarantee termination
    for p in procs:
        if p.poll() is None:
            try:
                p.kill()
                p.wait(timeout=6)
            except subprocess.TimeoutExpired:
                pass


def _load_shards(shard_paths: list[Path]) -> list[dict]:
    reports = []
    for shard_path in shard_paths:
        if shard_path.exists():
            try:
                reports.append(json.loads(shard_path.read_text()))
            except Exception as exc:
                sys.stderr.write(f"[merge] shard {shard_path} ungueltig: {exc}\n")
        else:
            sys.stderr.write(f"[merge] shard {shard_path} fehlt (Chunk fehlgeschlagen)\n")
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description="Sharded earnings scan (split + merge)")
    parser.add_argument("--report-type", default="BEFORE_OPEN",
                        choices=["BEFORE_OPEN", "AFTER_CLOSE"])
    parser.add_argument("--target-date", default=None)
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--min-market-cap", type=float, default=2_000_000_000)
    parser.add_argument("--exclude-prefixes", default="OTC:")
    parser.add_argument("--max-symbols", type=int, default=24)
    parser.add_argument("--chunk-size", type=int, default=4,
                        help="Symbols per parallel scan chunk (rate-limit safe)")
    parser.add_argument("--per-chunk-deadline", type=float, default=380.0,
                        help="Wall-clock budget per chunk in seconds")
    parser.add_argument("--discovery-timeout", type=float, default=120.0,
                        help="Timeout in seconds for the single discovery call")
    parser.add_argument("--tvremix-secret", default="tvremix API.txt")
    parser.add_argument("--finnhub-key", default="Finhub Key.txt")
    parser.add_argument("--out-dir", default="data/reports")
    args = parser.parse_args()

    # ── discovery (bounded by separate timeout, not shrinking) ──────────
    t_start = time.monotonic()
    symbols = _discover_symbols(args, timeout=args.discovery_timeout)
    discover_elapsed = time.monotonic() - t_start
    if not symbols:
        print(f"📅 {args.report_type.replace('_', ' ')} — keine Symbole gefunden.")
        return 0

    chunk_deadline = args.per_chunk_deadline

    # Dedupe once so dual-class pairs are never split across chunks
    symbols = dedupe_dual_class_symbols(symbols)
    sys.stderr.write(
        f"[plan] {len(symbols)} Symbole, chunk-size {args.chunk_size}, "
        f"{chunk_deadline:.0f}s pro Chunk, discovery {discover_elapsed:.0f}s\n"
    )

    # ── launch all chunks with stagger ────────────────────────────────
    # Each chunk is delayed by SPAWN_STAGGER seconds so TVRemix sees a
    # staggered stream of requests instead of N simultaneous floods → 429.
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
            "--deadline-seconds", str(chunk_deadline),
            "--tvremix-secret", args.tvremix_secret,
            "--finnhub-key", args.finnhub_key,
        ], capture=False))
        if index > 0:
            time.sleep(SPAWN_STAGGER)  # stagger to avoid 429

    # ── wait for all chunks, each with its own deadline ─────────────────
    # Every chunk gets the FULL per-chunk-deadline to work, independent of how
    # long other chunks take. The scheduler's 600s cron timeout is the
    # absolute outer safety net — no shrinking budget needed here.
    _wait_all(procs, deadline=chunk_deadline)
    chunk_elapsed = time.monotonic() - t_start
    reports = _load_shards(shard_paths)

    if not reports:
        print("📅 Scan fehlgeschlagen (keine Shard-Ergebnisse).")
        return 1

    merged = merge_reports(reports, report_type=args.report_type)

    # ── detect lost symbols → parallel rescue ──────────────────────────
    reported = {c["symbol"] for report in reports for c in report.get("candidates", [])}
    removed = set()
    for report in reports:
        removed |= set(report.get("quality", {}).get("removed_duplicate_symbols", []) or [])
    expected = set(symbols) | removed
    lost = sorted(expected - reported)
    merged["quality"]["lost_symbols"] = lost

    if lost:
        merged["quality"]["truncated"] = True
        sys.stderr.write(f"[verlust] {len(lost)} Symbol(e) fehlen: {', '.join(lost)}\n")

        # Parallel rescue: all lost symbols in one batch, each gets 120s
        rescue_timeout = 90.0
        sys.stderr.write(f"[rescue] starte {len(lost)} parallele Rettungen, je {rescue_timeout:.0f}s\n")
        rescue_procs: list[subprocess.Popen] = []
        rescue_paths: list[Path] = []
        for sym in lost:
            rescue_path = work / f"rescue_{sym.replace(':', '_')}.json"
            rescue_paths.append(rescue_path)
            rescue_procs.append(_run(args, [
                "--symbols", sym,
                "--report-type", args.report_type,
                "--as-of", args.as_of or "",
                "--out-file", str(rescue_path),
                "--deadline-seconds", str(rescue_timeout),
                "--tvremix-secret", args.tvremix_secret,
                "--finnhub-key", args.finnhub_key,
            ], capture=False))

        _wait_all(rescue_procs, deadline=rescue_timeout)
        rescue_reports = _load_shards(rescue_paths)
        rescued_count = len(rescue_reports)
        sys.stderr.write(f"[rescue] {rescued_count}/{len(lost)} gerettet\n")
        reports.extend(rescue_reports)

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
                merged["quality"]["truncated"] = any(
                    bool(r.get("quality", {}).get("truncated")) for r in reports
                )

    total_elapsed = time.monotonic() - t_start
    quality = merged["quality"]

    # ── write & render ─────────────────────────────────────────────────
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_id = merged["report_id"].replace(":", "_")
    out_path = out_dir / f"{safe_id}.json"
    out_path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")

    print(render_report(merged))

    sys.stderr.write(f"\n[artifact] {out_path}\n")
    sys.stderr.write(
        f"[quality] candidates={quality['candidate_count']} "
        f"incomplete={quality['incomplete_count']} "
        f"truncated={quality.get('truncated', False)} "
        f"shards={len(reports)}/{len(shard_paths)}\n"
    )
    sys.stderr.write(f"[timing] total {total_elapsed:.0f}s (discovery {discover_elapsed:.0f}s)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())