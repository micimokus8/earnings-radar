#!/usr/bin/env python3
"""Deterministic dry-run: fixture in, report file out. No network."""

from __future__ import annotations

import argparse
import json
import pathlib

from earnings_monitor.replay import run_fixture_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a fixture into a report file.")
    parser.add_argument("--fixture", required=True, help="Path to fixture JSON")
    parser.add_argument(
        "--out-dir",
        default="data/reports",
        help="Directory for the generated report file",
    )
    args = parser.parse_args()

    report = run_fixture_report(args.fixture)

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_id = report["report_id"].replace(":", "_")
    out_path = out_dir / f"{safe_id}.json"
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    quality = report["quality"]
    print(f"report_id={report['report_id']}")
    print(f"file={out_path}")
    print(
        "candidates={candidate_count} incomplete={incomplete_count}".format(**quality)
    )


if __name__ == "__main__":
    main()

      
