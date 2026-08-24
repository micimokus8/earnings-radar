from __future__ import annotations

from datetime import datetime, timedelta


_NEGATIVE_TERMS = ("investigation", "fraud", "lawsuit", "bankruptcy", "restatement", "offering")


def evaluate_news(headlines, *, as_of: str, window_days: int = 7) -> dict:
    if headlines is None:
        return {"status": "UNKNOWN", "negative_news": None, "matches": []}
    cutoff = datetime.fromisoformat(as_of) - timedelta(days=window_days)
    matches = []
    for item in headlines:
        try:
            published = datetime.fromisoformat(item["published"])
            headline = str(item["headline"])
        except (KeyError, TypeError, ValueError):
            continue
        if cutoff <= published <= datetime.fromisoformat(as_of):
            lowered = headline.casefold()
            terms = [term for term in _NEGATIVE_TERMS if term in lowered]
            if terms:
                matches.append({"headline": headline, "terms": terms, "published": item["published"]})
    return {"status": "FAIL" if matches else "PASS", "negative_news": bool(matches), "matches": matches}


__all__ = ["evaluate_news"]
