"""LLM interpretation layer: Pump-Challenger per candidate + final ranking.

The LLM evaluates pump potential based on the deterministic data (oversold +
room to high + squeeze + analyst surprise). It NEVER changes points or labels.
Output uses stable delimiters that the caller parses back into a structured dict.
"""

from __future__ import annotations

import json
import urllib.request

_SYSTEM_PROMPT = (
    "Du bist ein Earnings-Pump-Analyst. Du bekommst Kandidaten aus einem "
    "deterministischen Scanner (0-14 Punkte, 4 Kategorien) PLUS Earnings-Hunt-"
    "Metriken (52W-Hoch, Abstand zum Hoch, 5-Tages-Change, Daily-Change, DTC). "
    "Dein Ziel: Bewerte das PUMP-POTENTIAL nach Earnings. Regeln: "
    "Interpretiere AUSSCHLIESSLICH die gelieferten Werte; erfinde keine Zahlen; "
    "ändere keine Punkte oder Labels. Fokus: Ist der Kandidat vor Earnings "
    "überverkauft mit viel Luft nach oben (Bounce-Katalysator) oder schon "
    "eingepreist (Run-up)? Short-Squeeze-Potential? Analysten-Surprise? "
    "Kein finanzieller Rat. Antworte auf Deutsch, nüchtern, kompakt."
)

_DEUTUNG_MARKER = "DEUTUNG:"
_EMPFEHLUNG_MARKER = "EMPFEHLUNG:"


def _candidate_block(candidate: dict) -> str:
    values = candidate.get("values", {})
    score = candidate.get("score", {})
    calendar = candidate.get("sources", {}).get("calendar", {})
    cats = score.get("categories", {})
    top_headline = candidate.get("top_headline")
    lines = [
        f"Symbol: {candidate.get('symbol')}",
        f"Label/Score: {score.get('label')} ({score.get('total_points', 0)}/14)",
        f"Skip-Reason: {score.get('skip_reason', 'keine')}",
        f"Earnings: {calendar.get('earnings_date')} ({calendar.get('earnings_timing')})",
        # Earnings-Hunt key metrics
        f"Preis: {values.get('price_1d')} · 52W-Hoch: {values.get('high_52w')} "
        f"· Abstand: {values.get('distance_to_52w_pct')}% · 5d-Change: {values.get('change_5d_pct')}% "
        f"· 1d-Change: {values.get('daily_change_pct')}%",
        f"RSI: {values.get('rsi_1d')} · ADX: {values.get('adx_1d')} · "
        f"P<EMA20: {values.get('price_1d') is not None and values.get('ema20_1d') is not None and values['price_1d'] < values['ema20_1d']}",
        f"Analysten: {cats.get('analyst_expectation', {}).get('points', 0)}/3 "
        f"(eps={values.get('eps_estimate')}, upside={values.get('target_upside_pct')}%, "
        f"rating={values.get('analyst_rating')})",
        f"Short: {cats.get('short_interest', {}).get('points', 0)}/3 "
        f"(short%={values.get('short_pct_outstanding')}, DTC={values.get('days_to_cover')})",
        f"News: {cats.get('news_and_sec', {}).get('points', 0)}/3 "
        f"(neg_news={values.get('negative_news')}, insider={values.get('insider_status')})",
    ]
    if top_headline:
        lines.append(f'Top-Headline: "{top_headline}"')
    return "\n".join(lines)


def build_prompt(candidates: list[dict]) -> str:
    blocks = "\n\n".join(_candidate_block(c) for c in candidates)
    markers = "\n".join(
        f"{_DEUTUNG_MARKER}{c.get('symbol')} ... PUMP-THESE: (1-2 Sätze warum Pump likely/unlikely) | RISIKO: (1 Satz was dagegen spricht) | SCORE-CONFLICT: (falls Score und Pump-Potential divergieren, sonst 'kein')"
        for c in candidates
    )
    return (
        "Kandidaten des heutigen Earnings-Scans (deterministisch, Skala 0-14):\n\n"
        f"{blocks}\n\n"
        "Liefere jetzt pro Kandidat eine PUMP-ANALYSE und am Ende ein "
        "Gesamt-Ranking nach PUMP-POTENTIAL (nicht nach Score). Top 3 Kandidaten "
        "mit Begründung. Verwende EXAKT dieses Format:\n\n"
        f"{markers}\n\n"
        f"{_EMPFEHLUNG_MARKER} ... Top 3 nach Pump-Potential mit je 1 Satz Begründung"
    )


def _default_requester(url, *, headers, timeout, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),  # noqa
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def interpret_candidates(
    candidates: list[dict],
    *,
    api_key: str,
    base_url: str,
    model: str,
    requester=_default_requester,
    timeout: float = 60.0,
) -> dict:
    """Return {'deutung': {symbol: text}, 'empfehlung': str} or empty on failure."""
    if not candidates:
        return {"deutung": {}, "empfehlung": ""}
    payload = {
        "model": model,
        "temperature": 0.4,
        "max_tokens": 1600,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(candidates)},
        ],
    }
    response = None
    error = None
    try:
        response = requester(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            payload=payload,
        )
        raw = response["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        error = repr(exc)
        raw = ""
    if not raw:
        finish = (response or {}).get("choices", [{}])[0].get("finish_reason")
        return {
            "deutung": {},
            "empfehlung": "",
            "error": error or f"leere Antwort (finish_reason={finish}; moegliche Ursache: Reasoning-Modell braucht mehr max_tokens)",
        }

    deutung = {}
    empfehlung = ""
    lines = raw.splitlines()
    for line in lines:
        stripped = line.strip()
        if str(stripped).upper().startswith(_DEUTUNG_MARKER):
            rest = stripped[len(_DEUTUNG_MARKER):].strip()
            if " " in rest:
                symbol, text = rest.split(" ", 1)
                deutung[symbol.lstrip('*:-"').strip()] = text.strip()
            continue
        if stripped.startswith(_EMPFEHLUNG_MARKER):
            empfehlung = stripped[len(_EMPFEHLUNG_MARKER):].strip()
    return {"deutung": deutung, "empfehlung": empfehlung}


__all__ = ["build_prompt", "interpret_candidates"]
