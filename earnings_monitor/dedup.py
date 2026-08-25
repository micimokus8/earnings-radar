"""Deduplicate dual-class share tickers (e.g. HEI / HEI.A, BRK.A / BRK.B).

When a company lists multiple share classes, screeners/calendars often return
each class as a separate symbol. For an earnings monitor this double-counts the
same underlying business in the ranking. We collapse a class-suffixed ticker onto
its common-share base when both are present, preferring the unsuffixed symbol.
"""

from __future__ import annotations

import re

# Matches a trailing share-class suffix: ".A", ".B", ".CL", ".CLASSA", ".CLASSB".
_CLASS_SUFFIX = re.compile(r"\.(A|B|CL|CLASS[AB])$", re.IGNORECASE)
_EXCHANGE_SEP = ":"


def _strip_exchange(symbol: str) -> str:
    return str(symbol).split(_EXCHANGE_SEP, 1)[-1].strip()


def _has_class_suffix(symbol: str) -> bool:
    return bool(_CLASS_SUFFIX.search(_strip_exchange(symbol)))


def _base(symbol: str) -> str:
    return _CLASS_SUFFIX.sub("", _strip_exchange(symbol)).upper()


def dedupe_dual_class_symbols(symbols):
    """Return symbols with dual-class duplicates collapsed to one per company.

    Original (first-appearance) order is preserved; when a base maps to both a
    plain and a class-suffixed ticker, the plain one wins.
    """
    groups: dict[str, dict] = {}
    for idx, sym in enumerate(symbols):
        if not sym:
            continue
        base = _base(sym)
        entry = groups.setdefault(base, {"first_idx": idx, "symbols": []})
        entry["symbols"].append(sym)

    chosen = []
    for info in groups.values():
        plain = [s for s in info["symbols"] if not _has_class_suffix(s)]
        pick = plain[0] if plain else info["symbols"][0]
        chosen.append((info["first_idx"], pick))

    chosen.sort(key=lambda item: item[0])
    return [sym for _, sym in chosen]


__all__ = ["dedupe_dual_class_symbols"]
