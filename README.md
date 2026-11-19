# Earnings Monitor

Deterministic earnings scan for US equities mit 4-Kategorie Scoring, Telegram-Delivery und optionalem LLM Pump-Challenger.

**Stack:** Hermes Agent cron → Python pipeline → TVRemix MCP data → Telegram

---

## Architecture

```
EarningsWhispers API──┐
                      ├── max 12 symbols ──▶ run_sharded.py ──▶ run_scan.py (3 Chunks à 4, parallel)
TVRemix Screener ($10B fallback) ──┘           │                    │
                                                │                    ├── SI (first, Nasdaq/Finnhub)
                                                │                    ├── forecast (Finnhub)
                                                │                    ├── technicals (TwelveData → Indikatoren lokal)
                                                │                    ├── news (Finnhub → Yahoo-RSS-Fallback)
                                                │                    └── SEC (insider/dilution, optional)
                                                │
                                                ├── Ticker-Filter (_is_valid_ticker) gegen Garbage
                                                ├── Firmennamen (Finnhub profile2) an jeden Kandidaten
                                                └── render_report() ──▶ Telegram (ungeschnitten, N Nachrichten)
```

### Discovery

Zwei-Stufen Symbol-Discovery, Hard Cap **12 Symbole** pro Lauf:

| Stufe | Quelle | Session-Filter | Notes |
|-------|--------|---------------|-------|
| **Primary** | [EarningsWhispers](https://www.earningswhispers.com) `/api/quickcaldata/{yyyymmdd}/{rt}` | `rt=1` (BTO), `rt=3` (ATC) | Kuratierte "Most Anticipated" Liste |
| **Fallback** | TVRemix `run_screener` | Datum-sortiert, `--min-market-cap 10B` | Füllt Lücken wenn EW < 12 (TVRemix ist seit 28.10. abgeschaltet → Fallback liefert meist nichts) |

**EW-Endpoint (28.10. geändert):** `/api/quickcaldata/<datum>/<session>` liefert 404.
Der Kalender nutzt jetzt `/api/caldata/<datum>` (~250 Einträge/Tag, nach Relevanz
sortiert) und filtert die Session clientseitig über `releaseTime`
(1 = before open, 3 = after close). Die Top-12 der Liste sind die Mega-Caps.

Die EW-Liste ist session-bewusst: BEFORE_OPEN scannt nur vor Börsenöffnung, AFTER_CLOSE nur nach Börsenschluss.

### Pipeline

`EarningsPipeline` (`pipeline.py`) verarbeitet Symbole **sequentiell innerhalb eines Chunks**. `run_sharded.py` startet 3 Chunks à 4 Symbole **parallel** (Subprozesse, 8s Stagger gegen 429). Pro Symbol 90s Timeout, pro Chunk 280s Deadline; alle Chunks teilen sich **eine absolute Deadline**.

**Source Order** (SI first — höchster Wert, fragilste Quelle):

1. **Short Interest** — Nasdaq API + Finnhub Fallback, `RetryWrapper` (2 Retries × 0.5s)
2. **Forecast** — Analyst Ratings, EPS-Schätzungen, Target-Preise (TVRemix, 3 interne Retries)
3. **Technicals** — OHLCV → 52W-Hoch, 60d-Resistance, RSI, ADX, EMA20/50, MACD — alles lokal berechnet (`indicators.py`)
4. **News** — Headlines (TVRemix, 3 Retries)
5. **SEC** — Insider-Form4 + Dilution-Filings (optional, via --sec-user-agent)

### Write-after-each-symbol

`run_scan.py` schreibt den Report JSON **nach jedem Kandidaten** via `_atomic_write()` (Tempfile + Rename). Ein Kill mitten im Lauf verliert maximal das aktuelle Symbol.

### Garbage-Symbol-Schutz

`run_sharded.py` filtert Discovery-Output mit `_is_valid_ticker()`: nur Großbuchstaben, Ziffern, Punkte, Bindestriche → erlaubt. Emoji, Kleinbuchstaben, Datumsstrings, deutsche Wörter → raus. "Keine Symbole"-Meldungen gehen nach **stderr**, nie nach stdout.

---

## Data Sources

| Quelle | Endpoint | Data | Retry |
|--------|----------|------|-------|
| **EarningsWhispers** | `GET /api/quickcaldata` | Kuratierte Symbol-Liste | None (Fallback wenn fail) |
| **TVRemix MCP** | `POST https://tvremix.xyz/api/mcp/v1` | Calendar, Forecasts, OHLCV, News, Quotes | 3× intern (429/502/503/504/Timeout) |
| **Nasdaq SI** | `GET api.nasdaq.com/api/quote/{ticker}/short-interest` | Short Interest, DTC, Settlement-Date | `RetryWrapper` 2× |
| **Finnhub** | `stock/profile2` + `stock/measure` | Shares Outstanding, Short Ratio (Fallback) | `RetryWrapper` 1× |
| **SEC EDGAR** | `data.sec.gov/submissions/CIK...` | Insider Form4, Dilution (S-1/S-3) | `RetryWrapper` 2× (optional, via User-Agent File) |

---

## Scoring — Pump-Potenzial vor der Zahl

Feste **8 Punkte**. Fehlende Daten geben 0 und verkleinern den Nenner nicht.
Die Anzeige ist „3 von 8 Punkten“ plus die gemessene Häufigkeit dieses
Technik-Stands. Das ist keine Gewinnchance.

| Kategorie | Max | Wann es Punkte gibt |
|-----------|-----|---------------------|
| **① Raum** | 2 | Mindestens 8 % unter dem 52-Wochen-Hoch (+1). Nächster Pivot-Widerstand 3–15 % über dem Kurs (+1). |
| **② Historie** | 2 | Mindestens 4 frühere Zahlen und Trefferquote der Schätzung ≥ 50 % (+1). Durchschnittliche Reaktion danach positiv (+1). Unbekannte Uhrzeit zählt nicht mit. |
| **③ Revisionen** | 2 | Kauf-Anteil der Analysten um mindestens 5 Punkte gestiegen (+1). Kursziel um mindestens 2 % gestiegen (+1). Ein einzelner „Buy“ zählt nicht. |
| **④ News** | 2 | Eine positive Schlagzeile (+1), zwei (+1). Schweigen gibt nichts. |

**Sperren** (kein Ranking, kein Grün): näher als 3 % am 52-Wochen-Hoch, RSI ≥ 75,
Stochastik %K ≥ 90, schwere negative Schlagzeile (Betrug, Klage, Insolvenz,
Untersuchung), gesenktes Kursziel oder klar gesunkener Kauf-Anteil.

Grün gibt es nur, wenn ein Technik-Punktestand in der öffentlichen Nachrechnung
auf beiden Horizonten klar besser war als die ganze Liste. Stand 3.11.2025
bis 17.11.2026, 3.660 große Earnings-Namen: die Liste machte am Folgetag im
Mittel +0,31 % und am Meldetag +0,28 %. Ein Technik-Punkt lag bei +0,34 % und
+0,40 %, der Folgetag also nur drei Hundertstel darüber. Zwei Punkte hatten
mehr Ausschläge nach oben und mehr Verluste, der Mittelwert war nicht besser.
**Deshalb ist nichts grün.** Die Häufigkeit steht trotzdem neben den Punkten.

Leerverkauf wird gezeigt, aber nicht bepunktet. Insider-„kein Verkauf“ und
„keine Kapitalerhöhung“ geben keine Punkte. Stichworte in Schlagzeilen sind
ganze Wörter: „commission“ ist kein „miss“.

### Labels

| Punkte | Label | Anzeige |
|--------|-------|---------|
| Sperre | `SKIP (GRUND)` | nicht in der Medaillenliste |
| mindestens 2, keine Sperre | `WATCH` | Beobachten, nicht grün |
| Technik-Stand schlägt die Liste | `STRONG_SETUP` | grün; aktuell erreicht das niemand |
| darunter | `SKIP` | schwach |
| kein RSI oder kein 52-Wochen-Hoch | kein Label | unvollständig |

Die letzte Tageskerze zählt nur, wenn die New Yorker Kasse für diesen Tag
schon geschlossen hat. Sonst bleiben RSI, Stochastik und das Hoch auf dem
letzten fertigen Tag. Der Abstand wird mit dem aktuellen Kurs gerechnet.

Signale landen in `data/ledger/snapshots.jsonl` und `signals.jsonl`
(Verzeichnis ist gitignored, Pfad über `EARNINGS_DATA_DIR` überschreibbar).
`scripts/pump_ledger.py resolve` wertet die Sitzung aus.
`scripts/pump_postmortem.py week` schreibt die gemessenen Quoten nach
`data/ledger/lessons.md`, das der LLM-Lauf lädt.

---

## Telegram-Output

**Zwei Nachrichten pro Scan** (deterministischer Report + LLM Interpretation):

Ein Hermes-Job reicht, weil Winter- und Sommerzeit sich um eine Stunde verschieben:

`*/15 16-20 * * 1-5` → `scripts/cron_stage.sh`

Das ist 11:00–15:30 New York im Winter und 12:00–16:30 im Sommer. Das Skript
schaut auf die Uhr in New York und macht nur zwei Dinge:

| Fenster vor dem Kassenschluss | Was passiert |
|-------------------------------|--------------|
| etwa 1,5 bis 5 Stunden (Mittag) | Vorauswahl speichern. Keine Empfehlung. |
| 25 bis 50 Minuten (Ziel 30–45) | Frische Kurse, RSI/Stochastik/Raum neu, Namen mit starkem Lauf seit dem Mittag raus. Nur das ist die Empfehlung. |
| sonst, und an frühen Schlusstagen ausserhalb | Nichts, leere Ausgabe. |

Nach Börsenschluss sind das die Namen, die heute Abend Zahlen bringen.
Vor der Eröffnung sind es die Namen vom nächsten Morgen. Der Einstieg ist
der Kurs dieser Schlusskontrolle, nicht ein späterer Schlusskurs.

Schwellen stehen optional in `Freshness.txt` (`ran_pct=5`, `drop_pct=5`):
mehr als 5 % seit dem Mittag gestiegen oder gefallen, dann Sperre.

| Cron-Job | Wann | Output |
|----------|------|--------|
| `cron_stage.sh` | alle 15 Min, 16:00–20:30 UTC, Mo–Fr | Vorauswahl oder Empfehlung, je nach New-York-Uhr |
| `earnings-resolve` | **23:30 UTC** Di–Sa | Auswertung ab dem Kurs der Schlusskontrolle |

**Telegram-Format:**
- Kopfzeile nennt die Sitzung und den Halt (vor der Eröffnung: Vortagsschluss bis Open/Close des Meldetags; nach Börsenschluss: Schluss bis Open/Close des Folgetags, Verkauf bei etwa +10 bis +20 %)
- Pro Symbol: „X von 8 Punkten“, die gemessene Häufigkeit, vier Kategorien, max. 2 Schlagzeilen
- Gesperrte Namen stehen nicht in der Rangliste
- Firmenname neben dem Ticker (`CNC (Centene Corp)`) — Finnhub profile2
- **Keine Kürzung mehr:** `max_chars` ist standardmäßig aus. Hermes splittet
  lange Reports selbst in so viele Telegram-Nachrichten wie nötig (`(1/3)`,
  `(1/4)`, …). `--max-chars N` bleibt als optionaler Hard-Cap.

### LLM-Steuerung (keine Code-Änderungen)

| File | Content | Effect |
|------|---------|--------|
| `LLM Enabled.txt` | `ON` / `OFF` | LLM Interpretation aktiv/deaktiv |
| `LLM Model.txt` | Model-Slug (aktuell `deepseek/deepseek-v4.1-flash`) | Model zur Laufzeit wechseln |
| `LLM Key.txt` | OpenRouter Key `sk-or-…` | Auth; fehlt → nur deterministisch |

### LLM Pump-Challenger (P5)

Der LLM-Prompt wurde für Earnings-Hunt umgebaut: statt Score-Interpretation bewertet er pro Kandidat:
- **PUMP-THESE**: Welche Faktoren sprechen für einen Post-Earnings-Pump (Oversold + Raum + Squeeze + Surprise)?
- **RISIKO**: Was spricht dagegen (Run-up, negatives Sentiment, schwache Analysten)?
- **SCORE-CONFLICT**: Wenn deterministischer Score und Pump-Potential divergieren → Flag.

Abschluss: Top-3-Ranking nach Pump-Potential (nicht nach Score).

Der LLM **ändert nie Scores oder Labels** — er liefert eine zweite, unabhängige Perspektive.

**Wo er läuft:** seit 28.10. im **Orchestrator** (`run_sharded.py`,
`_interpret_merged`) — **ein** Call auf dem gemergten Report. Vorher rief
`run_sharded.py` den Worker ohne `--interpret` auf, und selbst mit Flag ginge
die LLM-Ausgabe der Chunk-Subprozesse ins `DEVNULL`: die Interpretation wurde
verworfen. `--no-llm` deaktiviert sie für einen Lauf.

**Reasoning-Modelle:** Sowohl `z-ai/glm-5.3-flash` als auch
`deepseek/deepseek-v4.1-flash` denken zuerst (`reasoning`) und liefern danach
`content`. Mit `max_tokens=1600` war das Budget am 28.10. komplett vom Denken
verbraucht → `content=null`, keine Interpretation. Deshalb: `max_tokens=6000`
(Denken + Antwort), `content` wird null-sicher gelesen, und der Fehlerpfad
nennt `finish_reason` + `reasoning_tokens`. Abschalten ließ sich `reasoning`
bei glm nicht per API (HTTP 400).

Messung mit dem echten 5-Kandidaten-Prompt (28.10.):

| Modell | Dauer | Reasoning | Kosten/Call |
|--------|-------|-----------|-------------|
| `z-ai/glm-5.3-flash` | 19–30s | ~1,5–3k Tokens | ~0,003 $ |
| **`deepseek/deepseek-v4.1-flash`** | **8–14s** | ~3k Tokens | ~0,0028 $ |

---

### Upstream-Limitierung: TVRemix (28.10.2026)

TVRemix antwortet inzwischen mit **HTTP 429** und einem Hinweis auf die
Abschaltung:

```json
{"error": "Rate limit exceeded. Retry after 27667s. The TradingView Remix MCP
 server is being shut down and is limited to 50 tool calls per day; use
 TradingView's official MCP server instead"}
```

Der Client hat `Retry-After` vorher **unbegrenzt** übernommen und schlief
7,7 Stunden → Cron-Timeout ohne Report. Jetzt:

- `Retry-After` wird auf `max_backoff` (8s) gekappt.
- Werte über `max_retry_after` (120s) lösen sofort
  `tvremix_rate_limited_long(...)` aus und öffnen einen **Circuit Breaker**
  für den restlichen Prozess — kein weiterer Netzwerkversuch.
- Ohne TVRemix bleiben Forecast/Technicals/News `UNKNOWN`; Kandidaten werden
  als `INCOMPLETE` gerendert, der Report erscheint trotzdem.

**Konsequenz (umgesetzt 28.10.):** Default-Datenquelle ist jetzt
**TwelveData** (OHLCV 1D/4H → EMA/RSI/ADX/MACD, 52W-Hoch, 5d/1d-Change lokal
berechnet) + **Finnhub** (Quote, Analysten-Rating, EPS aus dem Earnings-Kalender,
News). TVRemix bleibt optional via `--use-tvremix` (Schema unverändert).
`stock/price-target` ist bei Finnhub Premium (403) → Kursziel-Upside fehlt,
das kostet max. 1 Punkt in `analyst_expectation`.

Der offizielle **TradingView-MCP** ist keine Alternative für den Cron: OAuth
2.1 ohne Key, aber laut FAQ nur für „personal, interactive use" — autonome,
geplante Requests sind ausdrücklich nicht unterstützt und Sessions können
ohne Re-Autorisierung verfallen.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_sharded.py` | **Orchestrator:** EW Discovery → Ticker-Filter → run_scan Subprocess → Merge → Render + Write. Von Cron aufgerufen. |
| `scripts/run_scan.py` | **Worker:** Erhält Symbol-Batch, führt Pipeline aus, schreibt inkrementelle Shards. Von `run_sharded.py` als Subprozess. `--max-chars 0` (Default) = ungeschnitten. |
| `scripts/cron_before_open.sh` | Cron-Einstieg BEFORE_OPEN (09:30 UTC). |
| `scripts/cron_after_close.sh` | Cron-Einstieg AFTER_CLOSE (16:30 UTC). |

**Chunks laufen sequenziell (Default).** Der TwelveData-Limiter (7,6 s pro
Request) ist prozessübergreifend per Datei-Lock serialisiert — parallele Chunks
bekommen je nur einen Bruchteil der Slots, reißen ihr eigenes Chunk-Deadline und
verlieren die letzten Symbole (28.10.: 3 von 12). Sequenziell: 12 Symbole in
259 s, 0 Verluste. `--chunk-workers N` schaltet Parallelität zurück, wenn eine
Quelle ohne Rate-Limit genutzt wird.

**Deployment:** In `~/.hermes/scripts/` liegen **echte Wrapper-Dateien**
(`exec bash <repo>/scripts/... "$@"`), **keine Symlinks**. Der Scheduler löst
Symlinks auf und blockt Ziele außerhalb von `~/.hermes/scripts`
(„script path resolves outside the scripts directory").
| `scripts/llm_second.py` | Liest deterministischen Report und sendet LLM Pump-Challenger Message. |
| `scripts/dry_run.py` | Network-free Replay aus Cached Fixtures. |

### run_sharded.py Flags

```
--report-type BEFORE_OPEN|AFTER_CLOSE
--max-symbols 12              # Hard Cap
--min-market-cap 10000000000  # Screener-Floor
--exclude-prefixes "OTC:"     # Ausgeschlossene Exchanges
--chunk-size 4                # 4 Symbole pro Chunk
--chunk-workers 1             # 1 = sequenziell (Default); TwelveData serialisiert ohnehin
--per-chunk-deadline 280      # Budget pro Chunk (gemeinsame Deadline)
--discovery-timeout 30        # Max Sekunden für EW + Screener
--use-tvremix                 # optional: TVRemix als Primary (Default aus)
--total-budget 540            # Gesamtbudget; Skript endet selbst VOR dem 600s-Cron-Timeout
--sec-user-agent "SEC User-Agent.txt"  # Optional: Insider/Dilution
```

### Timing Budget

```
Discovery (EW + Fallback):     30s
Spawn-Stagger (3 Chunks):      16s
Chunks (parallel, 1 Deadline): 280s
Rescue (parallel, 1 Deadline):  90s
──────────────────────────────────
Total max:                    416s
Harte Selbstgrenze:           540s (--total-budget) < 600s Cron-Timeout
```

Wichtig: `_wait_all()` benutzt **eine absolute Deadline** für alle Prozesse.
Vorher bekam jeder Prozess die volle Deadline ab seinem Wartezeitpunkt —
3 × 280s = 840s und damit garantiert über dem 600s-Timeout (28.10., kein
Report). Die Rettung wird übersprungen, wenn weniger als 25s Budget übrig
sind, statt den Lauf zu sprengen.

---

## Key Modules

| Module | Responsibility |
|--------|---------------|
| `earnings_monitor/earningswhispers.py` | EW API Client, Session-bewusste Discovery |
| `earnings_monitor/pipeline.py` | Source Orchestrierung, Retry-Policy, Symbol-Deadlines |
| `earnings_monitor/scoring.py` | 14-Punkt Scoring + SKIP-Override für Earnings-Hunt |
| `earnings_monitor/candidate.py` | Flattet Source-Outputs zu normalized values dict |
| `earnings_monitor/report_builder.py` | Baut Report aus Candidates, Merge-Logik |
| `earnings_monitor/telegram_report.py` | Rendert Report zu Telegram-Text (2 Headlines, Raum-Zeile) |
| `earnings_monitor/short_interest_provider.py` | Nasdaq SI + Finnhub Fallback, Exchange-Aware |
| `earnings_monitor/indicators.py` | EMA20/50, ADX, MACD, 52W-Hoch, 60d-High, DailyChange, Distance-to-High |
| `earnings_monitor/technicals_normalizer.py` | Normalisiert OHLCV + Technicals zu Score-Feldern |
| `earnings_monitor/wiring.py` | Verkabelt Clients, `RetryWrapper`, SEC-Konfiguration |
| `earnings_monitor/tvremix_http.py` | Low-Level HTTP mit 429-aware Retry |
| `earnings_monitor/llm_interpretation.py` | Pump-Challenger Prompt + Parser |

---

## Security Rules

- Keine Order-Ausführung
- Keine API-Keys im Repository
- Secrets in lokalen Files (mode 600), nie committed
- Alle Timestamps UTC intern, Telegram in Europe/Berlin
- Jeder Score-Punkt ist auf konkrete Daten + Quelle rückführbar
- Gleicher Input → gleicher Output (deterministisch, bis auf LLM)
- Keine stille Daten-Imputation; fehlende Daten = `UNKNOWN` oder `N/A`