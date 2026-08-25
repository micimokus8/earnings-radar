#!/usr/bin/env bash
# Earnings monitor - BEFORE_OPEN scan (Mo-Fr 09:30 UTC). Deterministic message only.
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
exec python3 scripts/run_scan.py \
  --auto-discover \
  --report-type BEFORE_OPEN \
  --max-symbols 12 \
  --min-market-cap 2000000000 \
  --exclude-prefixes "OTC:"