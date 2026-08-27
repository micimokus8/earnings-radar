# Earnings Monitor

Deterministic earnings scan for US equities with a 4-category scoring system and Telegram delivery.

**Stack:** Hermes Agent cron → Python pipeline → TVRemix MCP data → Telegram output

---

## Architecture

```
EarningsWhispers API──┐
                      ├── max 12 symbols ──▶ run_sharded.py ──▶ run_scan.py (parallel chunks)
TVRemix Screener ($10B fallback) ──┘                              │
                                                                   ├── SI (first)
                                                                   ├── forecast
                                                                   ├── technicals
                                                                   └── news (last)
                                                                   │
                                                   write-after-each-symbol (atomic)
                                                                   │
                                                   render_report() ──▶ Telegram
```

### Discovery

Two-layer symbol discovery, with a hard cap of **12 symbols** per run:

| Layer | Source | Session filter | Notes |
|-------|--------|---------------|-------|
| **Primary** | [EarningsWhispers API](https://www.earningswhispers.com) `/api/quickcaldata/{yyyymmdd}/{rt}` | `rt=1` (BTO), `rt=3` (ATC) | Curated "Most Anticipated" list, sorted by trader attention |
| **Fallback** | TVRemix `run_screener` | date-sorted, `--min-market-cap 10B` | Fills remaining slots if EW returns < 12 |

The EW list is session-aware: a BEFORE_OPEN scan only pulls symbols reporting before the open, and AFTER_CLOSE only after-hours reporters.

### Pipeline

`EarningsPipeline` (`pipeline.py`) processes symbols sequentially **within** a chunk, but all chunks run in **parallel** subprocesses.

**Source order** (SI first — highest value, most fragile):

1. **Short Interest** — Nasdaq API + Finnhub fallback, wrapped in `RetryWrapper` (2 retries × 0.5s backoff)
2. **Forecast** — analyst ratings, EPS estimates, target prices (TVRemix, 3 internal retries)
3. **Technicals** — OHLCV → local EMA20/EMA50/ADX/RSI calculation (`indicators.py`)
4. **News** — headlines (TVRemix, 3 internal retries)

**Bounded execution:**

- **Symbol timeout:** 90s per symbol — if a single symbol's sources exceed this, the rest are marked `symbol_deadline_exceeded` and the pipeline moves to the next symbol
- **Chunk deadline:** 290s per subprocess chunk — all symbols within must complete or be truncated
- **Hard outer limit:** 600s Hermes cron timeout — the scheduler's kill switch, never approached in normal operation

### Write-after-each-symbol

`run_scan.py` writes the report JSON **after every candidate** via `_atomic_write()` (tempfile + rename). A mid-run kill (timeout, OOM) loses at most the one symbol currently being processed — all previously completed symbols are already on disk.

---

## Data Sources

| Source | Endpoint | Data | Retry |
|--------|----------|------|-------|
| **EarningsWhispers** | `GET /api/quickcaldata` | Curated "Most Anticipated" symbol list | None (fallback if fail) |
| **TVRemix MCP** | `POST https://tvremix.xyz/api/mcp/v1` | Calendar, forecasts, technicals (OHLCV), news, quotes | 3 attempts, exponential backoff (429/502/503/504/timeout) |
| **Nasdaq SI** | `GET api.nasdaq.com/api/quote/{ticker}/short-interest` | Short interest, days-to-cover, settlement date | `RetryWrapper` 2 attempts |
| **Finnhub** | `stock/profile2` + `stock/measure` | Shares outstanding, short ratio (fallback) | `RetryWrapper` 1 attempt |
| **SEC EDGAR** | `data.sec.gov/submissions/CIK...` | Insider filings (Form 4), dilution (S-1, S-3, etc.) | `RetryWrapper` 2 attempts (optional, requires User-Agent file) |

### Retry policy

- **TVRemix sources** (calendar, forecasts, technicals, news): retry 3× internally via `tvremix_http.` — **no** pipeline-level retry (avoids multiplicative explosion)
- **Nasdaq SI, Finnhub, SEC**: wrapped in `RetryWrapper` with bounded retries (1–2) since they have **no** internal retry logic
- Pipeline-level: `retries=0`

---

## Scoring

Four categories, 14 points max:

| Category | Max points | Key rules |
|----------|-----------|-----------|
| **① Analyst Expectation** | 3 | Upside > 30% (+1), positive EPS (+1), target recently cut (+1). **N/A** (0 pts) when no analyst coverage exists at all (`target_upside_pct` and `target_recently_cut` both None) |
| **② Short Interest** | 3 | Short % > 10% (+1), > 15% (+1), days-to-cover > 3 (+1). **N/A** for NYSE/AMEX (no Nasdaq SI data) |
| **③ Chart Confirmation** | 5 | 3 price/EMA rules + RSI < 40 + ADX < 25. **Capped at 2/5** when all three EMA rules are bearish (prevents a falling knife from generating WATCH) |
| **④ News & SEC** | 3 | No negative news (+1), no insider selling (+1), no dilution filing (+1) |

### Labels

| Score | Label | Meaning |
|-------|-------|---------|
| ≥ 10 | **STRONG_SETUP** | High-conviction candidate |
| 6–9 | **WATCH** | Potential setup, needs review |
| < 6 | **SKIP** | Weak or missing data |
| — | None | Candidate has missing core fields (INCOMPLETE) |

A candidate is `INCOMPLETE` if any of its core fields (`price`, `eps_estimate`, `ohlcv_1d`, `market_cap`, `short_pct_outstanding`, `days_to_cover`) are None. Incomplete candidates display scores but never receive a label or LLM interpretation.

---

## Telegram Output

**Two messages per scan** (deterministic report + LLM interpretation):

| Cron job | Schedule (Mo–Fr) | What it sends |
|----------|------------------|---------------|
| `earnings-before-open` | **09:30 UTC** (11:30 DE) | Deterministic report: scores, category breakdown, ranking |
| `earnings-before-llm` | **09:45 UTC** (11:45 DE) | LLM interpretation (2–3 sentence analysis + recommendation) |
| `earnings-after-close` | **16:30 UTC** (18:30 DE) | Deterministic report |
| `earnings-after-llm` | **16:45 UTC** (18:45 DE) | LLM interpretation |

Delivery target: Telegram chat `8686978363`. Both scan jobs use `no_agent=true` (stdout piped directly), the LLM jobs are LLM-driven.

### LLM controls (no code edits needed)

| File | Content | Effect |
|------|---------|--------|
| `LLM Enabled.txt` | `ON` / `OFF` | Enable/disable LLM interpretation |
| `LLM Model.txt` | Model slug (e.g. `openai/gpt-4o-mini`) | Swap model at runtime |
| `LLM Key.txt` | OpenRouter key `sk-or-…` | Auth; missing → deterministic only |

Only the **interpretation** and **recommendation** are LLM-generated. Everything else (scores, ranks, category breakdowns) is deterministic.

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_sharded.py` | **Orchestrator:** EW discovery → split into parallel chunks → merge shards → render + write report. Called by cron. |
| `scripts/run_scan.py` | **Worker:** receives a symbol batch, runs the pipeline, writes incremental shards. Called by `run_sharded.py` as subprocess. |
| `scripts/llm_second.py` | Reads the latest deterministic report and sends an LLM interpretation message. |
| `scripts/dry_run.py` | Network-free replay from cached fixtures. |

### run_sharded.py flags

```
--report-type BEFORE_OPEN|AFTER_CLOSE
--max-symbols 12              # Hard cap (EW + fallback)
--min-market-cap 10000000000  # Fallback universe floor
--exclude-prefixes "OTC:"     # Excluded exchanges
--chunk-size 3                # Symbols per parallel worker
--per-chunk-deadline 290      # Seconds per worker
--discovery-timeout 30        # Max seconds for EW + screener
```

---

## Key Modules

| Module | Responsibility |
|--------|---------------|
| `earnings_monitor/earningswhispers.py` | EW API client, session-aware symbol discovery |
| `earnings_monitor/pipeline.py` | Source orchestration, retry policy, symbol-level deadlines |
| `earnings_monitor/scoring.py` | 14-point scoring with N/A logic for missing coverage |
| `earnings_monitor/candidate.py` | Flattens source outputs into a normalized values dict |
| `earnings_monitor/report_builder.py` | Assembles candidate list into a report, merge logic |
| `earnings_monitor/telegram_report.py` | Renders report to formatted Telegram text |
| `earnings_monitor/short_interest_provider.py` | Nasdaq SI + Finnhub fallback with exchange-awareness |
| `earnings_monitor/indicators.py` | EMA20/EMA50/ADX from OHLCV candles |
| `earnings_monitor/wiring.py` | Wires real clients into the pipeline, `RetryWrapper` helper |
| `earnings_monitor/tvremix_http.py` | Low-level HTTP requester with 429-aware retry |

### Probe/utility scripts

- `scripts/probe_screener_*.py` — TVRemix screener diagnostics
- `scripts/probe_mcp.py`, `scripts/probe_tools_list.py` — MCP session probes
- `scripts/probe_calendar_*.py` — Calendar format discovery

---

## Timing Budget

```
Discovery (EW + fallback):   30s
4 chunks × 290s (parallel):  290s (wall clock = slowest chunk)
Rescue (parallel):            90s
────────────────────────────────
Total max:                  410s  << 600s (Hermes cron timeout)
```

---

## Security Rules

- No order execution
- No API keys in the repository
- Secrets stored in local files (mode 600), never committed
- All timestamps in UTC internally, rendered in Europe/Berlin
- Every score point is traceable to a concrete data value and source
- Same input → same output (deterministic)
- No silent data imputation; missing data is `UNKNOWN` or `N/A`