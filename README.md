# Earnings Monitor

Deterministic earnings scan for US equities mit 4-Kategorie Scoring, Telegram-Delivery und optionalem LLM Pump-Challenger.

**Stack:** Hermes Agent cron → Python pipeline → TVRemix MCP data → Telegram

---

## Architecture

```
EarningsWhispers API──┐
                      ├── max 12 symbols ──▶ run_sharded.py ──▶ run_scan.py (1 chunk, alle parallel)
TVRemix Screener ($10B fallback) ──┘           │                    │
                                                │                    ├── SI (first)
                                                │                    ├── forecast
                                                │                    ├── technicals → OHLCV → indicators
                                                │                    ├── news
                                                │                    └── SEC (insider/dilution, optional)
                                                │
                                                ├── Ticker-Filter (_is_valid_ticker) gegen Garbage
                                                └── render_report() ──▶ Telegram
```

### Discovery

Zwei-Stufen Symbol-Discovery, Hard Cap **12 Symbole** pro Lauf:

| Stufe | Quelle | Session-Filter | Notes |
|-------|--------|---------------|-------|
| **Primary** | [EarningsWhispers](https://www.earningswhispers.com) `/api/quickcaldata/{yyyymmdd}/{rt}` | `rt=1` (BTO), `rt=3` (ATC) | Kuratierte "Most Anticipated" Liste |
| **Fallback** | TVRemix `run_screener` | Datum-sortiert, `--min-market-cap 10B` | Füllt Lücken wenn EW < 12 |

Die EW-Liste ist session-bewusst: BEFORE_OPEN scannt nur vor Börsenöffnung, AFTER_CLOSE nur nach Börsenschluss.

### Pipeline

`EarningsPipeline` (`pipeline.py`) verarbeitet Symbole **sequentiell innerhalb eines Chunks**. Einziger Chunk mit `--chunk-size 12` (Parallelisierung über Subprozesse). Pro Symbol 90s Timeout, gesamter Chunk 540s Deadline.

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

## Scoring — Earnings-Hunt kalibriert

Vier Kategorien, max **14 Punkte**. Ausrichtung: Post-Earnings-Pump-Potential (Bounce + Raum + Squeeze + Überraschung).

| Kategorie | Max | Earnings-Hunt Logik |
|-----------|-----|---------------------|
| **① Analyst Expectation** | 3 | Upside >30% (+1), EPS ≤0 → Surprise-Potential (+1), Rating Strong Buy/Buy (+1), Target gesenkt (+1). **N/A** wenn keine Coverage |
| **② Short Interest** | 3 | DTC >3 (+1), >5 (+1); Short% >3% (+1), >8% (+1). Max 3. **N/A** bei Exchange ohne SI-Daten |
| **③ Chart Confirmation** | 5 | **Bounce-Setup:** RSI<40 (+1), P<EMA20 (+1). **Raum nach oben:** >15% unterm 52W-Hoch (+1), >30% (+1). **Pre-Earnings-Schutz:** 5d-Change <+10% (+1) |
| **④ News & SEC** | 3 | Keine neg. News (+1), kein Insider-Sell (+1), kein Dilution-Filing (+1) |

### SKIP-Override (überschreibt Score)

| Regel | Auslöser | Effect |
|-------|----------|--------|
| **EINGEPREIST** | `change_5d_pct ≥ 15%` UND `distance_to_52w > -10%` | 🔴 SKIP — Run-up zu nah am Hoch |
| **OVERBOUGHT** | `RSI_1d > 75` | 🔴 SKIP — überkauft |
| **POST_EARNINGS_CRASH** | `daily_change_pct ≤ -10%` | 🔴 SKIP — LULU-Fall |

### Labels

| Punkte | Label | Bedeutung |
|--------|-------|-----------|
| ≥ 10 | **STRONG_SETUP** 🟢🟢 | Earnings-Pump-Kandidat |
| 6–9 | **WATCH** 🟢 | Potenzial, Review nötig |
| < 6 oder SKIP-Override | **SKIP** ⚪/🔴 | Schwach oder Risiko |
| — | None | Core-Felder fehlen (INCOMPLETE) |

### Was der neue Score für AOUT/BBCP bedeutet

**AOUT** (Pre-Earnings: $9.96, RSI 26.9, 52W $14.97):
- Chart: RSI<40 (+1) + P<EMA20 (+1) + dist -33.5% (+2) + 5d +3% (+1) = **5/5**
- Analyst: Upside 43.5% + EPS negativ + Strong Buy + Target gesenkt = **3/3**
- Short: DTC 4.53 (+1) + Short% 1.62% (+0) = **1/3**
- **Total: 10/14 → STRONG_SETUP** (vorher 7/14 WATCH) ✓

**BBCP** (Pre-Earnings: $8.83, RSI 33.2, 52W $12.19):
- Chart: RSI<40 (+1) + P<EMA20 (+1) + dist -27.6% (+1) + 5d +5% (+1) = **4/5**
- Short: DTC 8.39 — new: >3 (+1) + >5 (+1) = **2/3** (vorher 1/3)
- **Total: 9/14 → WATCH** (vorher 6/14) ✓

---

## Telegram-Output

**Zwei Nachrichten pro Scan** (deterministischer Report + LLM Interpretation):

| Cron-Job | Schedule (Mo–Fr) | Output |
|----------|------------------|--------|
| `earnings-before-open` | **09:30 UTC** | Deterministischer Report: Score, Kategorie-Details, Ranking |
| `earnings-before-llm` | **09:45 UTC** | LLM Pump-Challenger Analyse |
| `earnings-after-close` | **16:30 UTC** | Deterministischer Report |
| `earnings-after-llm` | **16:45 UTC** | LLM Pump-Challenger Analyse |

**Telegram-Format:**
- Pro Symbol: Header (Emoji + Score + Label), 4 Kategorie-Zeilen, max **2 Headlines**
- Chart-Zeile zeigt zusätzlich: `52W $14.97 (-33.50%)·5d 3.00%·1d -5.00%`
- 🔴 bei SKIP-Override (EINGEPREIST, OVERBOUGHT, POST_EARNINGS_CRASH)
- Ranking: Top 10 nach Score geordnet

### LLM-Steuerung (keine Code-Änderungen)

| File | Content | Effect |
|------|---------|--------|
| `LLM Enabled.txt` | `ON` / `OFF` | LLM Interpretation aktiv/deaktiv |
| `LLM Model.txt` | Model-Slug (z.B. `openai/gpt-4o-mini`) | Model zur Laufzeit wechseln |
| `LLM Key.txt` | OpenRouter Key `sk-or-…` | Auth; fehlt → nur deterministisch |

### LLM Pump-Challenger (P5)

Der LLM-Prompt wurde für Earnings-Hunt umgebaut: statt Score-Interpretation bewertet er pro Kandidat:
- **PUMP-THESE**: Welche Faktoren sprechen für einen Post-Earnings-Pump (Oversold + Raum + Squeeze + Surprise)?
- **RISIKO**: Was spricht dagegen (Run-up, negatives Sentiment, schwache Analysten)?
- **SCORE-CONFLICT**: Wenn deterministischer Score und Pump-Potential divergieren → Flag.

Abschluss: Top-3-Ranking nach Pump-Potential (nicht nach Score).

Der LLM **ändert nie Scores oder Labels** — er liefert eine zweite, unabhängige Perspektive.

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_sharded.py` | **Orchestrator:** EW Discovery → Ticker-Filter → run_scan Subprocess → Merge → Render + Write. Von Cron aufgerufen. |
| `scripts/run_scan.py` | **Worker:** Erhält Symbol-Batch, führt Pipeline aus, schreibt inkrementelle Shards. Von `run_sharded.py` als Subprozess. |
| `scripts/llm_second.py` | Liest deterministischen Report und sendet LLM Pump-Challenger Message. |
| `scripts/dry_run.py` | Network-free Replay aus Cached Fixtures. |

### run_sharded.py Flags

```
--report-type BEFORE_OPEN|AFTER_CLOSE
--max-symbols 12              # Hard Cap
--min-market-cap 10000000000  # Screener-Floor
--exclude-prefixes "OTC:"     # Ausgeschlossene Exchanges
--chunk-size 12               # Ein Chunk (alle Symbole parallel)
--per-chunk-deadline 540      # Budget pro Chunk
--discovery-timeout 30        # Max Sekunden für EW + Screener
--sec-user-agent "SEC User-Agent.txt"  # Optional: Insider/Dilution
```

### Timing Budget

```
Discovery (EW + Fallback):    30s
1 chunk × 12 Symbole × 90s:  540s (deadline)
Rescue (parallel):             90s
──────────────────────────────────
Total max:                   660s  → vom 600s Cron-Timeout abgefangen
```

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