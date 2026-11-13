#!/usr/bin/env bash
# Pump-Ledger Pipeline: holt nach US-Close die Schlusskurse, verbucht
# PUMP/FLAT/REINFALL und laesst direkt danach das LLM-Postmortem laufen
# (war die Vorab-These bestaetigt/widerlegt + Zuender + Lesson).
# Laeuft taeglich 00:20 lokal (Di-Sa frueh).
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
export TWELVEDATA_API_KEY="$(cat 'TwelveData Key.txt')"

python3 scripts/pump_ledger.py resolve
rc=$?
# Postmortem ist idempotent: bewertet nur Outcomes ohne bestehenden Eintrag.
python3 scripts/pump_postmortem.py run >&2 || true
exit $rc
