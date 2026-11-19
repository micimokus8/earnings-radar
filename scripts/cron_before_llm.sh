#!/usr/bin/env bash
# BEFORE_OPEN LLM, 15 Minuten nach dem Abend-Scan.
# Hermes-Cron: 15 23 * * 1-5  (23:15 UTC = 18:15 EST / 19:15 EDT)
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
exec python3 scripts/llm_second.py --report-type BEFORE_OPEN