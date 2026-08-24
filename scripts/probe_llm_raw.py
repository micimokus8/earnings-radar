#!/usr/bin/env python3
"""Probe raw LLM response format through the real OpenRouter path."""

from __future__ import annotations

from earnings_monitor.llm_interpretation import build_prompt
from earnings_monitor.wiring import load_optional_text
import json


def main() -> None:
    import urllib.request

    api_key = load_optional_text("Deepseek Key.txt")
    model = load_optional_text("LLM Model.txt") or "stealth/ox-alpha"
    print("model:", repr(model), "key:", bool(api_key))

    cand = [{
        "symbol": "NASDAQ:ZM", "status": "PASS", "missing": [],
        "score": {
            "total_points": 5, "label": "SKIP",
            "categories": {"analyst_expectation": {"points": 1},
                           "short_interest": {"points": 0},
                           "chart_confirmation": {"points": 2},
                           "news_and_sec": {"points": 2}},
        },
        "values": {
            "price": 53.6, "eps_estimate": 1.48, "target_upside_pct": 12.3,
            "target_recently_cut": False, "short_pct_outstanding": 2.46,
            "days_to_cover": 2.3, "price_1d": 53.0, "price_4h": 54.0,
            "ema20_1d": 52.0, "ema50_1d": 50.0, "rsi_1d": 57.5, "adx_1d": 22.0,
            "news_status": "UNKNOWN", "negative_news": None,
            "insider_status": "UNKNOWN", "dilution_status": "UNKNOWN"},
        "sources": {"calendar": {"earnings_date": "2026-08-25",
                                  "earnings_timing": "AFTER_CLOSE"}},
    }]
    payload = {
        "model": model, "temperature": 0.4, "max_tokens": 900,
        "messages": [
            {"role": "system", "content": ("Du bist ein vorsichtiger "
             "Earnings-Analyst. Antworte deutsch kompakt.")},
            {"role": "user", "content": build_prompt(cand)},
        ],
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}",
                  "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    print("top-level keys:", list(body.keys()))
    choice = body.get("choices", [{}])[0]
    msg = choice.get("message", {})
    print("message keys:", list(msg.keys()))
    print("content:", repr(msg.get("content")))
    print("reasoning_content:", repr((msg.get("reasoning_content") or "")[:200]))
    print("finish_reason:", choice.get("finish_reason"))
    # honour any not-OK status
    if "error" in body:
        print("API ERROR:", body["error"])


if __name__ == "__main__":
    main()