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
    target = _num(v.get("target_average"), "$" )
    analyst_txt = f"Upside {upside}·PT {target}·EPS {eps}"
    rating = v.get("analyst_rating")
    if rating:
        analyst_txt += f"·Rating {rating}"
    if cut is True:
        analyst_txt += "·⚠ Target gesenkt"
    elif cut is False:
        analyst_txt += "·Target stabil"
    forecast_source = ((candidate.get("sources") or {}).get("forecast") or {}).get("forecast", {}).get("eps_source")
    if forecast_source == "finnhub_earnings_calendar":
        analyst_txt += "·EPS Kalender"
    target_status = ((candidate.get("sources") or {}).get("forecast") or {}).get("forecast", {}).get("target_status")
    if target_status == "REJECTED_MISMATCH":
        analyst_txt += "·PT verworfen (Einheiten/Währung inkonsistent)"
    elif v.get("target_upside_pct") is None:
        analyst_txt += "·Target Free-Tier gesperrt"
    forecast_error = ((candidate.get("sources") or {}).get("forecast") or {}).get("error")
    if forecast_error and "HTTP 403" in forecast_error:
        analyst_txt += "·EPS/Target HTTP 403"

    sp = v.get("short_pct_outstanding")
    dtc = v.get("days_to_cover")
    si_source = (candidate.get("sources") or {}).get("short_interest") or {}
    si_status = si_source.get("status", "UNKNOWN")
    si_date = si_source.get("report_date")
    if v.get("short_interest_supported") is False or si_status == "N/A":
        short_txt = "N/A (Quelle nicht unterstützt)"
    elif sp is not None and dtc is not None:
        short_txt = f"Short {_num(sp, '%')} · DTC {_num(dtc, digits=1)}"
        if si_date:
            short_txt += f" · Stand {si_date}"
    elif si_status == "PARTIAL":
        short_txt = "PARTIAL (SI unvollständig)"
        if dtc is not None:
            short_txt += f" · DTC {_num(dtc, digits=1)}"
    else:
        error = si_source.get("error")
        short_txt = "UNKNOWN (SI nicht verfügbar)"
        if error:
            short_txt += f" · {str(error)[:60]}"

    rsi = v.get("rsi_1d")
    e20, e50 = v.get("ema20_1d"), v.get("ema50_1d")
    p1 = v.get("price_1d")
    below = ""
    if p1 is not None and e20 is not None:
        below = "·P<EMA20" if p1 < e20 else "·P>EMA20"
    ema_txt = ""
    if e20 is not None and e50 is not None:
        ema_txt = f"·EMA20{'<' if e20 < e50 else '>'}EMA50"
    adx = v.get("adx_1d")
    p4 = v.get("price_4h")
    macd = v.get("macd_1d")
    macd_signal = v.get("macd_signal_1d")
    macd_hist = v.get("macd_histogram_1d")
    chart_price_txt = f"Preis: P1D {_num(p1)} · P4H {_num(p4)}"
    chart_trend_txt = f"Trend: RSI {_num(rsi, digits=1)} · ADX {_num(adx, digits=1)}{below}{ema_txt}"
    if macd is not None and macd_signal is not None:
        chart_momentum_txt = (f"Momentum: MACD {_num(macd, digits=3)} / "
                              f"Signal {_num(macd_signal, digits=3)} · "
                              f"Hist {_num(macd_hist, digits=3)}")
    else:
        chart_momentum_txt = "Momentum: MACD n/a"

    neg = v.get("negative_news")
    if neg is True:
        news_txt = "⚠ negative News"
    elif neg is False:
        news_txt = "keine neg. News"
    else:
        news_txt = "News UNKNOWN (0 Treffer)"
    if v.get("insider_status") in ("NO_DIRECT_SELL", "NO_RECENT_FILING_FOUND"):
        news_txt += "·kein Insider-Sell"
    # Show real provider titles, not an LLM-generated summary.
    headline_lines = []
    source = candidate.get("news_source")
    if source:
        news_txt += f"·Quelle {source}"
    # Providers do not guarantee order. Render newest dated headlines first,
    # keep undated items last, and use the original position as a stable tie-break.
    headlines = [item for item in (candidate.get("headlines") or []) if isinstance(item, dict)]
    ordered_headlines = sorted(
        enumerate(headlines),
        key=lambda pair: (pair[1].get("published") or "", -pair[0]),
        reverse=True,
    )
    for _, item in ordered_headlines[:5]:
        title = item.get("headline")
        if title:
            short = str(title).strip()
            if len(short) > 120:
                short = short[:117] + "…"
            headline_lines.append(f'    • “{short}”')
    return [
        f"| ① Analysten | {analyst_txt} | +{a_pts} |",
        f"| ② Short     | {short_txt} | +{si_pts} |",
        f"| ③ Chart     | {chart_price_txt} | +{ch_pts} |",
        f"|             | {chart_trend_txt} |",
        f"|             | {chart_momentum_txt} |",
        f"| ④ News/SEC  | {news_txt} | +{nw_pts} |",
    ] + headline_lines


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
        key=lambda c: (
            -((c.get("score") or {}).get("total_points", 0) or 0),
            _ticker(c.get("symbol", "?")).upper(),
        ),
    )
    for i, c in enumerate(ranked[:10], 1):
        ticker = _ticker(c.get("symbol", "?"))
        sc = (c.get("score") or {}).get("total_points", 0) or 0
        raw_label = (c.get("score") or {}).get("label")
        label = _LABEL_DE.get(raw_label, "unvollständig") if raw_label else "unvollständig"
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