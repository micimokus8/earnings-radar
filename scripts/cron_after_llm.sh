#!/usr/bin/env bash
# Earnings monitor - AFTER_CLOSE LLM message (Mo-Fr 16:45 UTC). Second message.
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
exec python3 scripts/llm_second.py --report-type AFTER_CLOSE