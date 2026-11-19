#!/usr/bin/env bash
# Pump-Ledger Pipeline: holt nach US-Close die Schlusskurse, verbucht
# PUMP/FLAT/REINFALL und laesst direkt danach das LLM-Postmortem laufen
# (war die Vorab-These bestaetigt/widerlegt + Zuender + Lesson).
# Nach dem US-Schluss, damit der Folgetag für AFTER_CLOSE schon einen Schluss hat.
# Hermes-Cron: 30 23 * * 2-6  (23:30 UTC = 18:30 EST / 19:30 EDT, Di–Sa).
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.
export TWELVEDATA_API_KEY="$(cat 'TwelveData Key.txt')"

python3 scripts/pump_ledger.py resolve
rc=$?
# Postmortem ist idempotent: bewertet nur Outcomes ohne bestehenden Eintrag.
python3 scripts/pump_postmortem.py run >&2 || true
exit $rc
