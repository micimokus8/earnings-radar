#!/usr/bin/env bash
# BEFORE_OPEN. Die Schlusskontrolle ist kurz vor dem US-Schluss des Vortags.
# Gleiche Uhr wie AFTER_CLOSE: scripts/cron_stage.sh. Dieser Wrapper läuft
# nur im Mittags- oder Schlussfenster und zielt sonst auf den nächsten Morgen.
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
exec python3 scripts/run_sharded.py \
  --stage auto \
  --report-type BEFORE_OPEN \
  --max-symbols 12 \
  --min-market-cap 10000000000 \
  --exclude-prefixes "OTC:" \
  --chunk-size 4 \
  --per-chunk-deadline 280 \
  --discovery-timeout 30 \
  --total-budget 540
