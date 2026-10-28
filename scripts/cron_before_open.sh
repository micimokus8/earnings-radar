#!/usr/bin/env bash
# Earnings monitor - BEFORE_OPEN scan (Mo-Fr 09:30 UTC). Deterministic message only.
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
exec python3 scripts/run_sharded.py \
  --report-type BEFORE_OPEN \
  --max-symbols 12 \
  --min-market-cap 10000000000 \
  --exclude-prefixes "OTC:" \
  --chunk-size 4 \
  --per-chunk-deadline 280 \
  --discovery-timeout 30 \
  --total-budget 540
