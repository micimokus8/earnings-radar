# Aktuelle LLM-Konfiguration (Earnings-Monitor)

Stand: 2026-11-03

## Modell
- **Modell:** `deepseek/deepseek-v4.1-flash`
- **Hinterlegt in:** `LLM Model.txt` (eine Zeile, wird von `load_optional_text()` gelesen)
- **Fallback (wenn Datei fehlt/leer):** `openai/gpt-4o-mini`
- **API-Endpunkt:** `https://openrouter.ai/api/v1`
- **Key:** `LLM Key.txt` (OpenRouter-Key)

## Parameter
| Parameter | Wert | Wo |
|---|---|---|
| `temperature` | 0.4 (Bewertung) / 0.3 (Postmortem) | `llm_interpretation.py` / `pump_postmortem.py` |
| `max_tokens` | **16000** | `llm_interpretation.py`, `pump_postmortem.py` |
| LLM-Timeout (intern) | **240 s** | `llm_second.py`, `pump_postmortem.py` |
| Script-Timeout (Cron) | 600 s | `~/.hermes/config.yaml` (`script_timeout_seconds`) |

## Warum 16000 max_tokens
`deepseek-v4.1-flash` ist ein **Reasoning-Modell**: Es verbraucht das Token-Budget
zuerst für internes Denken (`reasoning_tokens`), erst danach für die Antwort.
Am 03.11.2026 um 16:45 lief der Lauf mit **6000** max_tokens in
`finish_reason=length` (6002 Reasoning-Tokens) → `content=null` → Cron-Exit 1.
Mit 16000 Tokens: Live-Test 03.11. 18:5x erfolgreich, 5 Deutungen + Empfehlung in 48 s.

## Modelleignung
Das Modell ist **nicht falsch**. Es ist ein starkes Reasoning-Modell, das für die
komplexe Pump-Bewertung (12 Kandidaten, viele Metriken) geeignet ist. Der Aussetzer
war eine **Budget-Konfiguration**, kein Modellfehler. Wenn Stabilität vor
Reasoning-Tiefe geht, wäre ein Nicht-Reasoning-Modell (z. B. `openai/gpt-4o-mini`)
schneller und weniger token-hungrig — dafür inhaltlich flacher.

## Fallback bei erneutem Fehler
Meldung `leere Antwort (finish_reason=length ...)` → `max_tokens` weiter erhöhen
oder `reasoning_effort` senken. Meldung `Timeout` → Timeout erhöhen.
Der Fehlerpfad steht in `earnings_monitor/llm_interpretation.py` (Zeilen ~138–147).
