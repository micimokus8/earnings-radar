#!/usr/bin/env bash
# AFTER_CLOSE Schlusskontrolle. Besser scripts/cron_stage.sh alle 15 Minuten
# von 16:00 bis 20:30 UTC aufrufen. Dieser Wrapper läuft nur, wenn die
# New-York-Uhr im Fenster liegt (Mittagsauswahl oder 30–45 Min vor dem Schluss).
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
exec python3 scripts/run_sharded.py \
  --stage auto \
  --report-type AFTER_CLOSE \
  --max-symbols 12 \
  --min-market-cap 10000000000 \
  --exclude-prefixes "OTC:" \
  --chunk-size 4 \
  --per-chunk-deadline 280 \
  --discovery-timeout 30 \
  --total-budget 540
