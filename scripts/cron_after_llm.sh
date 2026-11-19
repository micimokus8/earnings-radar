#!/usr/bin/env bash
# AFTER_CLOSE LLM, 15 Minuten nach dem Scan.
# Hermes-Cron: 15 19 * * 1-5  (19:15 UTC = 14:15 EST / 15:15 EDT)
# Nach der LLM-Bewertung werden die Kandidaten (Merkmale + Vorher-Preis) in den
# Pump-Ledger geschrieben (snapshot, idempotent). Logs nach stderr, damit die
# Telegram-Nachricht aus stdout sauber bleibt.
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.

python3 scripts/llm_second.py --report-type AFTER_CLOSE
rc=$?

# Ledger-Snapshot vorbereiten (blockiert die Nachricht nicht)
if [ -f scripts/pump_ledger.py ]; then
  python3 scripts/pump_ledger.py snapshot >&2 || true
fi

exit $rc