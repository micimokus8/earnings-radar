#!/usr/bin/env bash
# Zwei Stufen, eine Uhr in New York. Hermes alle 15 Minuten:
#   */15 16-20 * * 1-5
# Das sind 11:00–15:30 New York im Winter und 12:00–16:30 im Sommer.
# Mittags speichert das Skript die Vorauswahl und schickt nichts.
# 25–50 Minuten vor dem Schluss (Ziel: 30–45 Minuten) schickt es die Empfehlung.
# Ausserhalb der Fenster bleibt die Ausgabe leer.
set -u
cd /root/.hermes/workspace/earnings-monitor || exit 1
export PYTHONPATH=.

stage=$(python3 -c 'from earnings_monitor.schedule import stage_for; print(stage_for("AFTER_CLOSE"))')
if [ "$stage" != "preselect" ] && [ "$stage" != "final" ]; then
  exit 0
fi

common=(
  --stage "$stage"
  --max-symbols 12
  --min-market-cap 10000000000
  --exclude-prefixes "OTC:"
  --chunk-size 4
  --per-chunk-deadline 280
  --discovery-timeout 30
  --total-budget 540
)

python3 scripts/run_sharded.py --report-type AFTER_CLOSE "${common[@]}"
rc=$?
python3 scripts/run_sharded.py --report-type BEFORE_OPEN "${common[@]}"
rc2=$?

if [ "$stage" = "final" ]; then
  python3 scripts/llm_second.py --report-type AFTER_CLOSE || true
  python3 scripts/llm_second.py --report-type BEFORE_OPEN || true
fi

if [ "$rc" -ne 0 ]; then
  exit "$rc"
fi
exit "$rc2"
