# Earnings Monitor

Deterministischer Earnings-Scan für US-Aktien mit vier Bewertungskategorien und Telegram-Ausgabe.

## Ziel

Der Monitor scannt Earnings-Aktien und bewertet sie anhand von:

1. Analysten-Erwartung (0–3 Punkte)
2. Short Interest (0–3 Punkte)
3. Chart-Bestätigung (0–5 Punkte)
4. News-Check (0–3 Punkte)

Gesamtscore: 0–14 Punkte.

Der Monitor bewertet **nicht**, ob eine Aktie bei Trade Republic, FinanzenZero oder einem anderen Neobroker kaufbar ist. Die Broker-Auswahl bleibt beim Nutzer.

## Scan-Zeitplan

- Morning Scan (`BEFORE_OPEN`): **09:30 UTC** (fachlich vorgemerkt; ursprünglich 09:00 UTC) — nach US-Eröffnung, vor dem Nachmittag
- Afternoon Scan (`AFTER_CLOSE`): **16:30 UTC** — nach Eröffnungsvolatilität, während US-Handelszeit
- Ausgabe-Zeitzone: Europe/Berlin
- Alle internen Zeitstempel: UTC

### Einschätzung zu 16:30 UTC

16:30 UTC entspricht 12:30 US/Eastern während der Sommerzeit. Das liegt 3,5 Stunden vor dem regulären US-Handelsschluss um 16:00 ET (20:00 UTC), nicht 4,5 Stunden. Für After-Close-Earnings ist das trotzdem ein sinnvoller Kompromiss: Der Scan ist nach der Eröffnungsvolatilität, aber noch während der US-Handelszeit. Es bleiben mehrere Stunden bis zu den meisten Veröffentlichungen.

Der Monitor darf daraus keine Kaufaufforderung ableiten. Er liefert Kandidaten, Score, Datenalter, Risiken und Earnings-Zeitpunkt.

## Datenadapter — verifiziert (Stand 13.08.2026)

Der TVRemix-MCP-Endpunkt ist live verifiziert (`initialize` + `tools/list`, Server 1.27.0, 58 Tools). Produktiv genutzte Tools mit jeweils einem echten Testaufruf:

| Tool | Verwendung |
|---|---|
| `get_earnings_calendar` | Earnings-Kalender (Batch) |
| `get_forecasts` | EPS-Schätzung, Targets, Upside |
| `get_quotes_batch` | Preis, Market Cap (Batch) |
| `get_technicals` | RSI (1D/4h); EMA/ADX liefert es **nicht** |
| `get_ohlcv` | Kerzen 1D/4h → lokale EMA20/EMA50/ADX-Berechnung |
| `get_news` | Headlines für 7-Tage-Newscheck |

SEC-Zugang separat über `data.sec.gov` (Submissions, Form-4-XML, Ticker-Mapping) mit eigenem User-Agent.

## Noch offene Entscheidungen / echte Blocker

Stand nach Implementierungsbeginn — gelöste Punkte sind markiert:

### 1. Short Interest — GELÖST (13.08.2026)

Live verifizierte Kette:

- **Shares Short / Days to Cover / Settlement-Date:** `api.nasdaq.com/api/quote/{SYM}/short-interest` (HTTP 200; konsolidierte FINRA-Daten über die Primärbörse)
- **Shares Outstanding:** Finnhub `stock/profile2` (`shareOutstanding`, Key nur lokal)
- Kombination in `short_interest_values.py`; Nenner ist **dokumentiert Shares Outstanding**, nicht Free Float
- **Frische-Gate: 45 Tage** — FINRA publiziert nur 2×/Monat (~9 Tage Lag), 10 Tage würden fast immer falsch `STALE` melden; Report-Datum bleibt sichtbar
- `days_to_cover > 3` = primäres Short-Signal; %-Schwellen (>10/>15) unverändert, aber auf Outstanding-Basis
- Live-Smoke AAPL/MSFT/NVDA: alle `PASS` (Report 31.07.2026)

Kein Phantomadapter, kein Fake-Nenner: fehlender Nenner → `PARTIAL`, Ausfall → `UNKNOWN`.

### 2. EMA100 — GELÖST

Der Technicals-Endpunkt liefert kein EMA100. Entscheidung umgesetzt: EMA20/EMA50/ADX werden deterministisch aus OHLCV-Kerzen (1D/4h) lokal berechnet und getestet (`indicators.py`). Kein stiller SMA-Ersatz.

### 3. Earnings-Zeitpunkt — GELÖST

Timing-Klassifizierung über Nasdaq-Felder implementiert (`nasdaq_timing.py`): `time-pre-market` → `BEFORE_OPEN`, `time-after-hours` → `AFTER_CLOSE`, unbekannt → explizit `UNKNOWN` (kein versteckter AMC-Default).

### 4. MCP-Verbindung — VERIFIZIERT

Live bestätigt: Streamable HTTP mit Bearer-Key, `initialize` + `tools/list` (58 Tools), je ein echter `tools/call` für alle genutzten Tools. Session-ID ist optional; der Server akzeptiert Aufrufe nach gültigem Initialize ohne Session-ID.

### 5. Batch-Fähigkeit und Toolumfang

Nur der Earnings-Kalender ist als Batch-Aufruf beschrieben. Klären:

- Können Forecasts, Technicals und News mehrere Symbole pro Call verarbeiten?
- Gibt es `tg_get_news_story` tatsächlich als verfügbares Tool, mit welchem Schema?
- Maximale Symbolanzahl pro Call und Fehlerverhalten bei Teilfehlern?

### 6. Analysten-Historie

Für „Target kürzlich gesenkt“ braucht der Monitor eigene Snapshots. Festlegen:

- Vergleichsfenster: 7 oder 14 Kalendertage,
- Vergleich: average target heute < letzter gültiger Snapshot,
- Mindestdifferenz gegen Rundungsrauschen,
- eigener Snapshot pro Symbol und UTC-Zeitpunkt.

### 7. News-/Dilution-Regeln

Fest definieren und testen:

- negative Headlines/Keywords und Zeitraum (7 Tage),
- positive/negative Priorität bei widersprüchlichen Headlines,
- Insider-Verkauf: News-Keyword ausreichend oder zusätzliche SEC-Quelle?
- Verwässerung: Welche Events zählen (S-1, S-3, 424B, ATM, offering, convertibles)?
- `tg_get_news_story` für Volltext oder nur Headlines?

### 8. Fehlende Daten

Nicht automatisch `0 Punkte` vergeben, weil das fehlende Daten wie ein negatives Signal behandelt. Empfohlener Zustand:

- Kategorie `UNKNOWN`,
- kein Gesamtscore bzw. `INCOMPLETE`,
- Kandidat separat als Datenlücke melden.

### 9. Universumfilter

Da Neobroker-Verfügbarkeit ausdrücklich nicht Aufgabe des Monitors ist, muss noch entschieden werden, ob der ursprüngliche Filter `Market Cap > $2 Mrd.` und NASDAQ/NYSE bestehen bleibt oder vollständig entfällt. Das ist kein Broker-Filter mehr, sondern ein Scan-Universum-Filter.

### 10. Score-Widersprüche

Die Beispiel-Einzelpunkte ergeben nicht die angegebenen Gesamtscores. Vor Implementierung müssen die Einzelregeln oder die Beispiel-Gesamtscores korrigiert werden. Der Code wird anschließend nur die Einzelregeln summieren.

### 11. Telegram und Cron-Betrieb

Noch festlegen:

- konkretes Telegram-Ziel,
- Hermes-Cron mit MCP oder eigener MCP-Client-Prozess,
- Secrets/Session-Storage,
- Retry-/Timeout-Verhalten und Alert bei unvollständigem Scan.

## Sicherheits-/Qualitätsregeln

- Keine Orderausführung
- Kein TradingView-API-Key im Repository
- Secrets ausschließlich über Umgebungsvariablen oder Hermes-Secrets
- Rohdaten, Normaldaten und Score-Ausgabe mit UTC-Timestamp speichern
- Jeder Punkt muss auf einen konkreten Datenwert und eine Quelle zurückführbar sein
- Gleicher Input muss immer denselben Score erzeugen
- Kein Score bei stillschweigender Datenveraltung oder fehlender Kernquelle

## Geplante Struktur

```text
config/
data/raw/
data/normalized/
data/snapshots/
data/reports/
src/earnings_monitor/
tests/fixtures/
tests/
deploy/
```

## Bot-Frage für die Architekturprüfung (beantwortet)

Die ursprünglichen Vertragsfragen (Toolnamen, Schemas, Transport, Rate Limits) sind zwischenzeitlich durch live verifizierte Aufrufe beantwortet — siehe „Verifizierter Status & Implementierungsstand“ unten. Der Abschnitt bleibt als Dokumentation der Prüf-Kriterien erhalten:

- Welche exakten Toolnamen gibt es?
- Sind sie aus einem Cron-Prozess heraus erreichbar?
- Gibt es MCP/HTTP/CLI?
- Wie lautet das vollständige Input-/Output-Schema je Tool?
- Liefert `technicals` tatsächlich 1D und 4H inklusive Rating, EMA und ADX?
- Liefert `forecasts` aktuelle und historische Target-Werte inklusive Änderungsdatum?
- Liefert `news` Veröffentlichungszeitpunkt, Quelle und Text/Headline?
- Welche Daten sind live, welche verzögert?
- Welche Authentifizierung und Rate Limits gelten?
- Gibt es einen getesteten Beispielaufruf mit JSON-Antwort?

Erst mit diesen Antworten wird der Datenadapter implementiert.

## Verifizierter Status & Implementierungsstand (13.08.2026)

### tvremix MCP — live verifiziert

```text
https://tvremix.xyz/api/mcp/v1
```

- `initialize` + `tools/list`: HTTP 200, Server 1.27.0, 58 Tools
- Echte `tools/call`-Proben bestanden für: `get_earnings_calendar`, `get_forecasts`, `get_quotes_batch`, `get_technicals`, `get_ohlcv`, `get_news`
- Session-ID optional; API-Key nur in lokaler Datei (Rechte 600), nie im Repo

### SEC — angebunden und orchestriert

- Ticker→CIK-Mapping, Submissions, Form-4-Parsing, Dilution-Klassifizierung
- Lookups in der Pipeline verdrahtet; Statussemantik: `NO_RECENT_FILING_FOUND`/`NO_DIRECT_SELL` = erfolgreiche Negativbefunde, `PARTIAL`/`UNKNOWN` getrennt
- Echte Read-only-Probe mit Apple-Form-4 bestanden (`M`/`F` sind keine Verkäufe)

### Pipeline · Reports · Replay · Telegram-Dry-Run

- Pipeline: Kalender+Quotes batchweise, Rest symbolweise; Quellfehler isoliert als `UNKNOWN`
- Kandidat: auditierbare `sources`, flache `values`, deterministischer 14-Punkte-Score
- Reports: getrennte Streams `BEFORE_OPEN`/`AFTER_CLOSE` mit stabilen IDs (`2026-08-13:BEFORE_OPEN`)
- Replay: netzwerkfreie Fixture-Läufe; `scripts/dry_run.py` schreibt Reportdateien nach `data/reports/`
- Runner: `scripts/run_scan.py` verbindet alle Live-Quellen end-to-end (TVRemix-MCP, SEC optional, Nasdaq-SI, Finnhub) → Reportdatei + gerenderten Telegram-Text
- **Tages-Discovery:** über den date-sortierten Screener (`run_screener`, limit 1000) mit client-seitigem Datumsfilter; Universe-Filter via `--min-market-cap`/`--exclude-prefixes`
- **Retry-Policy:** transiente Quellenfehler/UNKNOWN werden in der Pipeline 2× mit Exponential-Backoff wiederholt
### Telegram-Ausgabe (aktiv)

Reiches Layout (siehe laufender Lauf in `data/reports/`):

```text
📊 AFTER CLOSE — Earnings <Datum>
⚪ ZM — Score: 1/14 — SKIP
| ① Analysten | Upside 12.3%·EPS 1.48 | +0 |
| ② Short     | Short 2.46%·DTC 2.3   | +0 |
| ③ Chart     | RSI 57.5·P>EMA20      | +1 |
| ④ News/SEC  | keine neg. News       | +0 |
Deutung: <LLM, 2-3 Sätze>
📊 RANKING  +  🎯 Meine Empfehlung <LLM>
```

**LLM-Anteil (nur diese beiden Textteile):** je Kandidat die **Deutung** und die finale **„Meine Empfehlung"**. Alles andere (Scores, Punkte, Ranking, Tabellen) ist deterministisch und immer vorhanden. INCOMPLETE-Kandidaten werden nie interpretiert.

### LLM schalten ohne Code

| Datei | Inhalt | Wirkung |
|---|---|---|
| `LLM Enabled.txt` | `ON` / `OFF` | LLM ein-/ausschalten (kein Key nötig für ON-Aus) |
| `LLM Model.txt` | Modell-Slug, z. B. `deepseek/deepseek-v4-flash-0731` | Modell tauschen, kein Code-Edit |
| `Deepseek Key.txt` | OpenRouter-Key (`sk-or-…`) | Auth; fehlt → nur deterministisch |

Übergabe im Runner: `--interpret` setzt LLM frei; Toggle-Datei entscheidet beim Lauf. Nachrichten werden bei 4096 Zeichen sauber gekürzt (Status in `data/reports/`).
- Testsuite: 169 deterministische Unit-Tests, alle grün

### Cron-Betrieb (aktiv seit 24.08.2026)

**Zwei Nachrichten pro Scan** (LLM ausgelagert, damit der deterministische Scan nie durch den LLM-Call blockiert wird):

| Job | ID | Zeit (Mo–Fr) | Inhalt |
|---|---|---|---|
| BEFORE_OPEN Scan | `cbeac85bce3d` | 09:30 UTC / 11:30 DE | deterministischer Report (Tabelle + Ranking) |
| BEFORE_OPEN LLM | `66f847314339` | 09:45 UTC / 11:45 DE | Deutung + „Meine Empfehlung" |
| AFTER_CLOSE Scan | `ec04cd95bd18` | 16:30 UTC / 18:30 DE | deterministischer Report |
| AFTER_CLOSE LLM | `42e71808997c` | 16:45 UTC / 18:45 DE | Deutung + „Meine Empfehlung" |

- Zustellung: Telegram-Chat `8686978363` (wie Kerdos); Modus `no_agent=true`, stdout 1:1 gesendet
- **Kein Wochenende** (`1-5`); keine Earnings am Tag → kurze Meldung „Keine Earnings-Daten gefunden …"
- **Cron-Timeout auf 600 s** erhöht (`cron.script_timeout_seconds` in `config.yaml`) — ausreichend für bis zu 40 Symbole
- Symbolumfang: bis zu 40 Symbole (kein harter 5er-Cap), Universe ≥ $2 Mrd., ohne OTC
- LLM-Job liest den deterministischen Report aus `data/reports/`; kein Key/kein Kandidat → kurze Hinweis-Meldung
- Modell tauschbar in `LLM Model.txt`, LLM ein/aus via `LLM Enabled.txt`

### Yahoo Short Interest (historische Probe, weiter offen)

- `fc.yahoo.com` setzte ein `A3`-Cookie, antwortete mit HTTP `404`.
- `getcrumb` und `quoteSummary`: HTTP `429`.

Yahoo bleibt damit nicht cron-stabil; benötigte Felder wären `shortPercentOfFloat`, `shortRatio`, `sharesShort`, `averageDailyVolume10Day`, `dateShortInterest`.

### Noch offen

1. Telegram-Ziel festlegen und Versand nach Dry-Run-Freigabe aktivieren
2. Fehler-/Retry-Prüfung im Betrieb, danach erst Cron-Diskussion

### Börsenkalender — GELÖST (13.08.2026)

`exchange_calendar.py` (rein stdlib, `zoneinfo`): NYSE-Feiertage inkl. Oster-Computus und Sa/So-Rollung, Frühschlusstage (13:00 ET), `trading_sessions()`, `completed_sessions_before()` mit DST-sensitiven Schlusszeiten — Integrationstest gegen die bestehende Stale-Logik vorhanden.
