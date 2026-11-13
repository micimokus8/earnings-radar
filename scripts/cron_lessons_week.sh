#!/usr/bin/env bash
# Wochen-Lessons: aggregiert die Postmortems der letzten 7 Tage zu
# data/ledger/lessons.md, das der LLM-Prompt der Tagesbewertung laedt.
# Laeuft sonntags 08:00 lokal.
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
exec python3 scripts/pump_postmortem.py week --days 7
