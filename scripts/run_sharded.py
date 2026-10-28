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
from earnings_monitor.llm_interpretation import interpret_candidates

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


def _read_optional(path: str, default: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip() or default
    except OSError:
        return default


_LLM_OFF = {"OFF", "NO", "AUS", "0", "FALSE"}


def _interpret_merged(merged, *, enabled: str, api_key: str, model: str,
                      base_url: str, interpreter=interpret_candidates):
    """LLM-Interpretation auf dem gemergten Report.

    Returns (deutung, empfehlung, note). Ein Call pro Report, nie pro Chunk:
    die Chunk-Subprozesse schreiben nach DEVNULL, ihre LLM-Ausgabe ginge
    verloren. Genau das war der Zustand bis 28.10.
    """
    if enabled.strip().upper() in _LLM_OFF:
        return {}, "", "LLM deaktiviert (LLM Enabled.txt = OFF)"
    if not api_key:
        return {}, "", "LLM aus - kein Key"
    labelled = [c for c in merged.get("candidates", [])
                if (c.get("score") or {}).get("label")]
    if not labelled:
        return {}, "", "LLM uebersprungen - keine bewertbaren Kandidaten"
    result = interpreter(labelled[:5], api_key=api_key, base_url=base_url,
                         model=model)
    deutung = result.get("deutung", {})
    empfehlung = result.get("empfehlung", "")
    if not deutung and not empfehlung:
        return {}, "", f"LLM fehlgeschlagen: {result.get('error', 'leer')}"
    return deutung, empfehlung, f"LLM ok ({model}, {len(deutung)} Symbole)"


def _is_valid_ticker(symbol: str) -> bool:
    """Filter garbage that would slip through stdout parsing."""
    if not symbol or len(symbol) > 10:
        return False
    # Tickers are uppercase letters, digits, dots, dashes (e.g. BF.B, BRK-A)
    return all(c.isupper() or c.isdigit() or c in ".-" for c in symbol)


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
    raw = result.stdout.split()
    # Defensive: filter out non-ticker garbage (emoji, German words, dates, etc.)
    # that could appear if run_scan prints a human message to stdout.
    valid = [s for s in raw if _is_valid_ticker(s)]
    if len(valid) != len(raw):
        sys.stderr.write(
            f"[discover] {len(raw) - len(valid)} ungueltige Token herausgefiltert: "
            f"{[s for s in raw if not _is_valid_ticker(s)]}\n"
        )
    return valid


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _wait_all(procs, deadline: float):
    """Wait for all processes against ONE shared absolute deadline.

    Vorher bekam jeder Prozess die volle Deadline ab dem Moment, in dem er
    an die Reihe kam: 3 Chunks x 280s = 840s und damit zuverlaessig ueber dem
    600s-Cron-Timeout (28.10.). Jetzt laeuft die Uhr einmal und alle teilen
    sich das Budget.
    """
    end = time.monotonic() + max(0.1, deadline)
    for p in procs:
        remaining = end - time.monotonic()
        # Nach Ablauf der gemeinsamen Deadline nicht mehr 0.1s pro Prozess
        # nachwarten — sonst waechst die Gesamtzeit wieder mit der Anzahl.
        if remaining <= 0 or p.poll() is not None:
            continue
        try:
            p.wait(timeout=remaining)
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


def _effective_chunk_deadline(per_chunk: float, budget_end: float,
                              now: float, reserve: float = 100.0) -> float:
    """Chunk-Deadline, gedeckelt durch das verbleibende Gesamtbudget.

    Reserve = 90s Rescue + 10s Merge/Render. Floor 60s, damit ein spaeter
    Start nicht in einen sinnlosen 5-Sekunden-Scan laeuft.
    """
    return min(float(per_chunk), max(60.0, budget_end - now - reserve))


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


def _bare_symbol(symbol: str) -> str:
    """Compare discovery tickers with resolver-qualified report symbols."""
    return str(symbol).split(":", 1)[-1].strip().upper()


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
    parser.add_argument("--total-budget", type=float, default=540.0,
                        help="Gesamtbudget in Sekunden; muss unter dem Cron-Timeout "
                             "(600s) bleiben, damit das Skript selbst sauber endet")
    parser.add_argument("--tvremix-secret", default="tvremix API.txt")
    parser.add_argument("--use-tvremix", action="store_true",
                        help="TVRemix als Primary (Default: aus, Dienst eingestellt)")
    parser.add_argument("--finnhub-key", default="Finhub Key.txt")
    parser.add_argument("--sec-user-agent", default="SEC User-Agent.txt",
                        help="File with SEC User-Agent string for insider/dilution lookups")
    parser.add_argument("--out-dir", default="data/reports")
    parser.add_argument("--llm-enabled-file", default="LLM Enabled.txt")
    parser.add_argument("--llm-key", default="LLM Key.txt")
    parser.add_argument("--llm-model-file", default="LLM Model.txt")
    parser.add_argument("--llm-base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--no-llm", action="store_true",
                        help="LLM-Interpretation fuer diesen Lauf deaktivieren")
    args = parser.parse_args()

    # ── discovery (bounded by separate timeout, not shrinking) ──────────
    t_start = time.monotonic()
    symbols = _discover_symbols(args, timeout=args.discovery_timeout)
    discover_elapsed = time.monotonic() - t_start
    if not symbols:
        sys.stderr.write(f"[scan] keine Symbole für {args.report_type} gefunden.\n")
        return 0

    budget_end = t_start + args.total_budget
    rescue_reserve = 100.0  # 90s Rescue + Reserve fuer Merge/Render
    chunk_deadline = _effective_chunk_deadline(
        args.per_chunk_deadline, budget_end, time.monotonic(), rescue_reserve,
    )

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
            "--sec-user-agent", args.sec_user_agent,
            *(["--use-tvremix"] if args.use_tvremix else []),
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
    reported = {_bare_symbol(c["symbol"]) for report in reports for c in report.get("candidates", [])}
    removed = set()
    for report in reports:
        removed |= set(report.get("quality", {}).get("removed_duplicate_symbols", []) or [])
    expected = {_bare_symbol(s) for s in symbols} | {_bare_symbol(s) for s in removed}
    lost = sorted(expected - reported)
    merged["quality"]["lost_symbols"] = lost

    if lost:
        merged["quality"]["truncated"] = True
        sys.stderr.write(f"[verlust] {len(lost)} Symbol(e) fehlen: {', '.join(lost)}\n")

        # Parallel rescue: alle verlorenen Symbole in EINEM Batch.
        # Budget wird aus dem Gesamtbudget abgeleitet, damit die Rettung den
        # Cron-Timeout nicht sprengt (vorher: 90s pro Symbol nacheinander).
        remaining = budget_end - time.monotonic()
        rescue_timeout = min(90.0, remaining - 15.0)
        rescue_procs: list[subprocess.Popen] = []
        rescue_paths: list[Path] = []

        if rescue_timeout < 25.0:
            sys.stderr.write(
                f"[rescue] uebersprungen - nur {max(0.0, remaining):.0f}s Budget uebrig "
                f"({len(lost)} Symbol(e) fehlen)\n")
        else:
            sys.stderr.write(
                f"[rescue] starte {len(lost)} parallele Rettungen, je {rescue_timeout:.0f}s\n")
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
                    "--sec-user-agent", args.sec_user_agent,
                    *(["--use-tvremix"] if args.use_tvremix else []),
                ], capture=False))
            _wait_all(rescue_procs, deadline=rescue_timeout)

        rescue_reports = _load_shards(rescue_paths)
        rescued_count = len(rescue_reports)
        sys.stderr.write(f"[rescue] {rescued_count}/{len(lost)} gerettet\n")
        reports.extend(rescue_reports)

        if reports:
            merged = merge_reports(reports, report_type=args.report_type)
            reported2 = {_bare_symbol(c["symbol"]) for r in reports for c in r.get("candidates", [])}
            removed2 = set()
            for r in reports:
                removed2 |= set(r.get("quality", {}).get("removed_duplicate_symbols", []) or [])
            expected2 = {_bare_symbol(s) for s in symbols} | {_bare_symbol(s) for s in removed2}
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

    # ── LLM-Interpretation: EIN Call auf dem gemergten Report ───────────
    # Vorher lief sie in run_scan.py pro Chunk — und deren stdout geht ins
    # DEVNULL, d.h. die Interpretation wurde verworfen. Ausserdem wurde
    # --interpret vom Orchestrator nie gesetzt. Ergebnis: LLM faktisch aus.
    deutung, empfehlung, llm_note = {}, "", ""
    if not args.no_llm:
        deutung, empfehlung, llm_note = _interpret_merged(
            merged,
            enabled=_read_optional(args.llm_enabled_file, "ON"),
            api_key=_read_optional(args.llm_key, ""),
            model=_read_optional(args.llm_model_file, "openai/gpt-4o-mini"),
            base_url=args.llm_base_url,
        )
    if llm_note:
        sys.stderr.write(f"[llm] {llm_note}\n")

    print(render_report(merged, deutung=deutung, empfehlung=empfehlung))

    sys.stderr.write(f"\n[artifact] {out_path}\n")
    sys.stderr.write(
        f"[quality] candidates={quality['candidate_count']} "
        f"incomplete={quality['incomplete_count']} "
        f"truncated={quality.get('truncated', False)} "
        f"shards={len(reports)}/{len(shard_paths)}\n"
    )
    sys.stderr.write(
        f"[timing] total {total_elapsed:.0f}s (budget {args.total_budget:.0f}s, "
        f"discovery {discover_elapsed:.0f}s, chunks {chunk_elapsed - discover_elapsed:.0f}s)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())