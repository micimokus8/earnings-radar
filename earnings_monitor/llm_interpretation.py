"""LLM interpretation layer: per-candidate Deutung + final Empfehlung.

The LLM explains deterministic results; it never computes points, invent
numbers, or produces trade recommendations. Output uses stable delimiters
that the caller parses back into a structured dict.
"""

from __future__ import annotations

import json
import urllib.request

_SYSTEM_PROMPT = (
    "Du bist ein vorsichtiger US-Earnings-Analyst. Du bekommst Kandidaten aus "
    "einem deterministischen Scanner (0-14 Punkte, 4 Kategorien). Regeln: "
    "Interpretiere AUSSCHLIESSLICH die gelieferten Werte; erfinde keine neuen "
    "Zahlen; ändere keine Punkte oder Labels; fehlende Daten sind Lücken, keine "
    "Negativsignale. Kein finanzieller Rat, keine Kauf-/Verkaufsaufforderung. "
    "Antworte auf Deutsch, nüchtern, kompakt."
)

_DEUTUNG_MARKER = "DEUTUNG:"
_EMPFEHLUNG_MARKER = "EMPFEHLUNG:"


def _candidate_block(candidate: dict) -> str:
    values = candidate.get("values", {})
    score = candidate.get("score", {})
    calendar = candidate.get("sources", {}).get("calendar", {})
    cats = score.get("categories", {})
    lines = [
        f"Symbol: {candidate.get('symbol')}",
        f"Label/Score: {score.get('label')} ({score.get('total_points', 0)}/14)",
        f"Earnings: {calendar.get('earnings_date')} ({calendar.get('earnings_timing')})",
        f"Analysten-Punkte: {cats.get('analyst_expectation', {}).get('points', 0)}/3 "
        f"(eps_est={values.get('eps_estimate')}, target_upside%={values.get('target_upside_pct')}, "
        f"target_recently_cut={values.get('target_recently_cut')})",
        f"Short-Punkte: {cats.get('short_interest', {}).get('points', 0)}/3 "
        f"(short%outstanding={values.get('short_pct_outstanding')}, days_to_cover={values.get('days_to_cover')})",
        f"Chart-Punkte: {cats.get('chart_confirmation', {}).get('points', 0)}/5 "
        f"(preis_1d={values.get('price_1d')}, preis_4h={values.get('price_4h')}, "
        f"ema20_1d={values.get('ema20_1d')}, ema50_1d={values.get('ema50_1d')}, "
        f"rsi_1d={values.get('rsi_1d')}, adx_1d={values.get('adx_1d')})",
        f"News-Punkte: {cats.get('news_and_sec', {}).get('points', 0)}/3 "
        f"(news_status={values.get('news_status')}, negative_news={values.get('negative_news')}, "
        f"insider={values.get('insider_status')}, dilution={values.get('dilution_status')})",
    ]
    return "\n".join(lines)


def build_prompt(candidates: list[dict]) -> str:
    blocks = "\n\n".join(_candidate_block(c) for c in candidates)
    markers = "\n".join(
        f"{_DEUTUNG_MARKER}{c.get('symbol')} ... 2-3 Saetze warum/ob lohnend"
        for c in candidates
    )
    return (
        "Kandidaten des heutigen Scans (deterministisch, Skala 0-14):\n\n"
        f"{blocks}\n\n"
        "Liefere jetzt für jeden Kandidat eine Deutung und am Ende ein "
        "Gesamt-Urteil + eine kompakte Empfehlung. Verwende EXAKT dieses Format, "
        "eine Zeile je Kandidat Deutung, Absatz danach EMPFEHLUNG:\n\n"
        f"{markers}"
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
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(candidates)},
        ],
    }
    try:
        response = requester(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            payload=payload,
        )
        raw = response["choices"][0]["message"]["content"].strip()
    except Exception:
        return {"deutung": {}, "empfehlung": ""}

    deutung = {}
    empfehlung = ""
    lines = raw.splitlines()
    for line in lines:
        stripped = line.strip()
        if str(stripped).upper().startswith(_DEUTUNG_MARKER):
            rest = stripped[len(_DEUTUNG_MARKER):].strip()
            if " " in rest:
                symbol, text = rest.split(" ", 1)
                deutung[symbol.lstrip("*:-").strip()] = text.strip()
            continue
        if stripped.startswith(_EMPFEHLUNG_MARKER):
            empfehlung = stripped[len(_EMPFEHLUNG_MARKER):].strip()
    return {"deutung": deutung, "empfehlung": empfehlung}


__all__ = ["build_prompt", "interpret_candidates"]