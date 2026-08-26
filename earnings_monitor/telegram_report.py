"""Rich plain-text rendering of an earnings report for Telegram.

Deterministic lines (tables/points/ranking) come from report data; the
optional LLM parts (per-candidate Deutung + final Empfehlung) are passed in
and appended, never merged into the score.
"""

from __future__ import annotations

_EMO = {"STRONG_SETUP": "🟢🟢", "WATCH": "🟢", "SKIP": "⚪"}
_LABEL_DE = {"STRONG_SETUP": "STARKES Setup", "WATCH": "Beobachten", "SKIP": "SKIP"}


def _ticker(symbol: str) -> str:
    return str(symbol).split(":")[-1].strip()


def _num(value, suffix="", digits=2):
    if value is None:
        return "n/a"
    try:
        text = f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"
    return f"{text}{suffix}"


def _candidate_header(candidate: dict, total: int, maxp: int) -> str:
    lab = (candidate.get("score") or {}).get("label")
    emoji = _EMO.get(lab, "◯")
    name = _ticker(candidate.get("symbol", "?"))
    if lab:
        return f"{emoji} {name} — Score: {total}/{maxp} — {_LABEL_DE.get(lab, lab)}"
    return f"{emoji} {name} — Score: {total}/{maxp} — ⚠ unvollständig"


def _candidate_rows(candidate: dict) -> list[str]:
    v = candidate.get("values", {})
    s = candidate.get("score", {})
    cats = s.get("categories", {})
    a_pts = (cats.get("analyst_expectation") or {}).get("points", 0)
    si_pts = (cats.get("short_interest") or {}).get("points", 0)
    ch_pts = (cats.get("chart_confirmation") or {}).get("points", 0)
    nw_pts = (cats.get("news_and_sec") or {}).get("points", 0)

    eps = _num(v.get("eps_estimate"))
    upside = _num(v.get("target_upside_pct"), "%")
    cut = v.get("target_recently_cut")
    analyst_txt = f"Upside {upside}·EPS {eps}"
    if cut is True:
        analyst_txt += "·⚠ Target gesenkt"
    elif cut is False:
        analyst_txt += "·Target stabil"

    sp = v.get("short_pct_outstanding")
    dtc = v.get("days_to_cover")
    if v.get("short_interest_supported") is False:
        short_txt = "n/a (nur NASDAQ-SI)"
    elif sp is not None and dtc is not None:
        short_txt = f"Short {_num(sp, '%')}·DTC {_num(dtc, digits=1)}"
    else:
        short_txt = "n/a (SI-Fehler)"

    rsi = v.get("rsi_1d")
    e20, e50 = v.get("ema20_1d"), v.get("ema50_1d")
    p1 = v.get("price_1d")
    below = ""
    if p1 is not None and e20 is not None:
        below = "·P<EMA20" if p1 < e20 else "·P>EMA20"
    ema_txt = ""
    if e20 is not None and e50 is not None:
        ema_txt = f"·EMA20{'<' if e20 < e50 else '>'}EMA50"
    chart_txt = f"RSI {_num(rsi, digits=1)}{below}{ema_txt}"

    neg = v.get("negative_news")
    if neg is True:
        news_txt = "⚠ negative News"
    elif neg is False:
        news_txt = "keine neg. News"
    else:
        news_txt = "News n/a"
    if v.get("insider_status") in ("NO_DIRECT_SELL", "NO_RECENT_FILING_FOUND"):
        news_txt += "·kein Insider-Sell"

    return [
        f"| ① Analysten | {analyst_txt} | +{a_pts} |",
        f"| ② Short     | {short_txt} | +{si_pts} |",
        f"| ③ Chart     | {chart_txt} | +{ch_pts} |",
        f"| ④ News/SEC  | {news_txt} | +{nw_pts} |",
    ]


def render_report(
    report: dict,
    *,
    deutung: dict | None = None,
    empfehlung: str | None = None,
    max_chars: int = 4096,
) -> str:
    deutung = deutung or {}
    empfehlung = (empfehlung or "").strip()
    rtype = report["report_type"]
    rdate = report["report_date"]
    truncated = bool((report.get("quality") or {}).get("truncated", False))
    lost = (report.get("quality") or {}).get("lost_symbols") or []
    header_line = f"📊 {rtype.replace('_', ' ')} — Earnings {rdate}"
    if lost:
        header_line += " · ⚠️ Verlorene Symbole: " + ", ".join(
            s.split(":")[-1] for s in lost[:6]
        ) + (" …" if len(lost) > 6 else "") + " (Scan unvollständig)"
    elif truncated:
        header_line += " · ⚠️ ggf. gekappt (Deadline)"
    lines = [header_line, ""]

    for candidate in report["candidates"]:
        sc = candidate.get("score") or {}
        total, maxp = sc.get("total_points", 0), sc.get("max_points", 14)
        lines.append(_candidate_header(candidate, total, maxp))
        lines.extend(_candidate_rows(candidate))
        d = deutung.get(candidate.get("symbol"))
        if d:
            lines.append(f"Deutung: {d}")
        elif candidate.get("status") != "PASS":
            lines.append("Deutung: — (Daten unvollständig)")
        lines.append("")

    lines.append("📊 RANKING")
    ranked = sorted(
        report["candidates"],
        key=lambda c: -((c.get("score") or {}).get("total_points", 0)),
    )
    for i, c in enumerate(ranked[:10], 1):
        ticker = _ticker(c.get("symbol", "?"))
        sc = (c.get("score") or {}).get("total_points", 0)
        label = (c.get("score") or {}).get("label") or "unvollständig"
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        lines.append(f"• {medal} {ticker} — {sc}/14 — {label}")

    if empfehlung:
        lines.append("")
        lines.append("🎯 Meine Empfehlung")
        lines.append(empfehlung)

    text = "\n".join(lines).rstrip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n… (Report gekürzt, vollständig in data/reports/)"


__all__ = ["render_report"]