"""Word-boundary headline tags. Substrings like 'commission' are not a 'miss'."""

from __future__ import annotations

import re

_SEVERE = (
    r"frauds?",
    r"bankruptc(?:y|ies)",
    r"lawsuits?",
    r"investigations?",
)
_SOFT = (
    r"miss(?:es|ed|ing)?",
    r"downgrades?",
    r"downgraded",
    r"warns",
    r"warnings?",
    r"recalls?",
    r"offerings?",
    r"dilutions?",
    r"restatements?",
)
_POSITIVE = (
    r"beats?",
    r"beaten",
    r"upgrades?",
    r"upgraded",
    r"buybacks?",
    r"approvals?",
    r"approved",
    r"partnerships?",
    r"raises guidance",
    r"raised guidance",
    r"guidance raised",
    r"record revenue",
    r"record profit",
)


def _compile(parts: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_SEVERE_RE = _compile(_SEVERE)
_SOFT_RE = _compile(_SOFT)
_POSITIVE_RE = _compile(_POSITIVE)


def classify_headline(text: str) -> dict:
    """Return severity and whether the headline is positive.

    A severe or soft negative match suppresses the positive flag. 'miss' does
    not match inside 'commission' or 'permission'.
    """
    title = str(text or "")
    severe = _SEVERE_RE.search(title) is not None
    soft = _SOFT_RE.search(title) is not None
    positive = _POSITIVE_RE.search(title) is not None and not severe and not soft
    if severe:
        severity = "severe"
    elif soft:
        severity = "soft"
    else:
        severity = None
    return {"severity": severity, "positive": positive}


def classify_headlines(titles: list[str]) -> dict:
    severe = 0
    soft = 0
    positive = 0
    for title in titles:
        tag = classify_headline(title)
        if tag["severity"] == "severe":
            severe += 1
        elif tag["severity"] == "soft":
            soft += 1
        elif tag["positive"]:
            positive += 1
    if severe:
        severity = "severe"
    elif soft:
        severity = "soft"
    else:
        severity = None
    return {
        "negative_news": bool(severity),
        "news_severity": severity,
        "positive_news_count": positive,
    }


__all__ = ["classify_headline", "classify_headlines"]
