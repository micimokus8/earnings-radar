from __future__ import annotations

from datetime import datetime, timedelta

from earnings_monitor.news_terms import classify_headline


def evaluate_news(headlines, *, as_of: str, window_days: int = 7) -> dict:
    if headlines is None:
        return {
            "status": "UNKNOWN",
            "negative_news": None,
            "news_severity": None,
            "positive_news_count": None,
            "matches": [],
        }
    cutoff = datetime.fromisoformat(as_of) - timedelta(days=window_days)
    kept = []
    for item in headlines:
        try:
            published = datetime.fromisoformat(item["published"])
            headline = str(item["headline"])
        except (KeyError, TypeError, ValueError):
            continue
        if cutoff <= published <= datetime.fromisoformat(as_of):
            kept.append(headline)
    tags = [classify_headline(title) for title in kept]
    matches = [
        {"headline": title, "severity": tag["severity"]}
        for title, tag in zip(kept, tags)
        if tag["severity"]
    ]
    positive = sum(1 for tag in tags if tag["positive"])
    if any(tag["severity"] == "severe" for tag in tags):
        severity = "severe"
    elif any(tag["severity"] == "soft" for tag in tags):
        severity = "soft"
    else:
        severity = None
    return {
        "status": "FAIL" if severity else "PASS",
        "negative_news": bool(severity),
        "news_severity": severity,
        "positive_news_count": positive,
        "matches": matches,
    }


__all__ = ["evaluate_news"]
