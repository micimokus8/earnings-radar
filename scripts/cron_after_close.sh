#!/usr/bin/env bash
# Earnings monitor - AFTER_CLOSE daily scan (16:30 UTC)
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
exec python3 scripts/run_scan.py \
  --auto-discover \
  --report-type AFTER_CLOSE \
  --interpret \
  --min-market-cap 2000000000 \
  --exclude-prefixes "OTC:"
