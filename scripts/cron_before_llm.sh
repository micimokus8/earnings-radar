#!/usr/bin/env bash
# Earnings monitor - BEFORE_OPEN LLM message (Mo-Fr 09:45 UTC). Second message.
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
exec python3 scripts/llm_second.py --report-type BEFORE_OPEN