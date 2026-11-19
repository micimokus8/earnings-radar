"""Rich plain-text rendering of an earnings report for Telegram.

Deterministic lines (tables/points/ranking) come from report data; the
optional LLM parts (per-candidate Deutung + final Empfehlung) are passed in
and appended, never merged into the score.
"""

from __future__ import annotations

_EMO = {"STRONG_SETUP": "🟢", "WATCH": "·", "SKIP": "⚪"}
_LABEL_DE = {
    "STRONG_SETUP": "Grün: historisch besser als die Liste",
    "WATCH": "Beobachten, nicht grün",
    "SKIP": "schwach",
}


def _default_horizon(report_type: str) -> str:
    if report_type == "AFTER_CLOSE":
        return (
            "Sitzung: Zahlen nach US-Schluss. Empfehlung 30–45 Minuten vor 16:00 New York. "
            "Einstieg ist der Kurs dieser Kontrolle. "
            "Halten bis zum nächsten Handelstag, Verkauf bei etwa +10 bis +20 %. "
            "Messung: dieser Kurs → Open und Close des Folgetags."
        )
    return (
        "Sitzung: Zahlen vor der Eröffnung. Empfehlung kurz vor dem Schluss des Vortags. "
        "Einstieg ist der Kurs dieser Kontrolle. "
        "Halten bis zum Meldetag, Verkauf bei etwa +10 bis +20 %. "
        "Messung: dieser Kurs → Open und Close des Meldetags."
    )


def _ticker(symbol: str) -> str:
    return str(symbol).split(":")[-1].strip()


def _display(candidate: dict) -> str:
    """Ticker plus Firmenname, z.B. 'CNC (Centene Corp)'."""
    ticker = _ticker(candidate.get("symbol", "?"))
    name = candidate.get("name")
    if not name:
        return ticker
    name = str(name).strip()
    if len(name) > 32:
        name = name[:29].rstrip() + "…"
    return f"{ticker} ({name})"


def _num(value, suffix="", digits=2):
    if value is None:
        return "n/a"
    try:
        text = f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"
    return f"{text}{suffix}"


def _score_text(score: dict) -> str:
    """'3 von 8 Punkten'. Die Prozentzahl ist keine Gewinnchance."""
    total = score.get("total_points", 0) or 0
    reachable = score.get("max_points") or score.get("reachable_points") or 8
    return f"{total} von {reachable} Punkten"


def _label_text(score: dict) -> str:
    lab = score.get("label")
    if not lab:
        return "unvollständig"
    if lab in _LABEL_DE:
        return _LABEL_DE[lab]
    if str(lab).startswith("SKIP ("):
        reason = str(lab)[len("SKIP ("):-1] if str(lab).endswith(")") else str(lab)
        return f"Sperre: {reason.replace('_', ' ').replace('+', ', ')}"
    return str(lab)


def _candidate_header(candidate: dict, total: int, maxp: int) -> str:
    score = candidate.get("score") or {}
    lab = score.get("label")
    emoji = _EMO.get(lab, "◯") if lab in _EMO or not lab else "⚪"
    if lab and str(lab).startswith("SKIP"):
        emoji = "⚪"
    name = _display(candidate)
    text = _score_text(score)
    note = score.get("frequency_note") or ""
    line = f"{emoji} {name} — {text} — {_label_text(score)}"
    if note:
        line += f"\n    {note}"
    return line


def _candidate_rows(candidate: dict) -> list[str]:
    v = candidate.get("values", {})
    s = candidate.get("score", {})
    cats = s.get("categories", {})
    room_pts = (cats.get("room") or {}).get("points", 0)
    hist_pts = (cats.get("history") or {}).get("points", 0)
    rev_pts = (cats.get("revisions") or {}).get("points", 0)
    news_pts = (cats.get("news") or {}).get("points", 0)

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
    h52 = v.get("high_52w")
    dist52 = v.get("distance_to_52w_pct")
    c5 = v.get("change_5d_pct")
    d1 = v.get("daily_change_pct")
    room_txt = ""
    if h52 is not None:
        room_txt = f"·52W {_num(h52, '$')}"
        if dist52 is not None:
            room_txt += f" ({_num(dist52, '%')})"
    if c5 is not None:
        room_txt += f"·5d {_num(c5, '%')}"
    if d1 is not None:
        room_txt += f"·1d {_num(d1, '%')}"
    chart_trend_txt = f"Trend: RSI {_num(rsi, digits=1)} · ADX {_num(adx, digits=1)}{below}{ema_txt}"
    if room_txt:
        chart_trend_txt += f" | {room_txt.lstrip('·')}"
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
    for _, item in ordered_headlines[:2]:
        title = item.get("headline")
        if title:
            short = str(title).strip()
            if len(short) > 120:
                short = short[:117] + "…"
            headline_lines.append(f'    • “{short}”')
    beat = v.get("beat_rate")
    beat_txt = "n/a" if beat is None else f"{float(beat) * 100:.0f}% ({v.get('beat_n') or 0} Zahlen)"
    hist = v.get("hist_reaction_pct")
    hist_txt = "n/a" if hist is None else f"{_num(hist, '%')} im Schnitt ({v.get('hist_n') or 0})"
    room = s.get("room_to_resistance_pct", v.get("room_to_resistance_pct"))
    dist = s.get("distance_to_52w_pct", v.get("distance_to_52w_pct"))
    stoch = v.get("stoch_k_1d")
    revision = v.get("analyst_revision") or "keine"
    target_rev = v.get("target_revision") or ("gesenkt" if cut is True else "keine")
    positive = v.get("positive_news_count")
    pos_txt = "n/a" if positive is None else str(positive)
    return [
        f"| ① Raum      | Abstand 52W {_num(dist, '%')} · bis Widerstand {_num(room, '%')} | +{room_pts} |",
        f"|             | {chart_price_txt} |",
        f"|             | {chart_trend_txt} · Stoch {_num(stoch, digits=0)} |",
        f"|             | {chart_momentum_txt} |",
        f"| ② Historie  | Schlägt Schätzung {beat_txt} · Reaktion {hist_txt} | +{hist_pts} |",
        f"| ③ Revision  | Analysten {revision} · Kursziel {target_rev} · {analyst_txt} | +{rev_pts} |",
        f"| ④ News      | positive Schlagzeilen {pos_txt} · {news_txt} | +{news_pts} |",
        f"|             | {short_txt} (nur Kontext, keine Punkte) |",
    ] + headline_lines


def render_report(
    report: dict,
    *,
    deutung: dict | None = None,
    empfehlung: str | None = None,
    max_chars: int | None = None,
) -> str:
    deutung = deutung or {}
    empfehlung = (empfehlung or "").strip()
    rtype = report["report_type"]
    rdate = report["report_date"]
    truncated = bool((report.get("quality") or {}).get("truncated", False))
    lost = (report.get("quality") or {}).get("lost_symbols") or []
    horizon = report.get("horizon") or _default_horizon(rtype)
    header_line = f"{rtype.replace('_', ' ')} — Earnings {rdate}"
    if report.get("priced_at_text"):
        header_line += f"\n{report['priced_at_text']}"
    header_line += f"\n{horizon}"
    if report.get("stage") == "final" and report.get("preselect_found") is False:
        header_line += "\nKeine Mittagsauswahl gefunden. Der Lauf seit dem Mittag wurde nicht geprüft."
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

    lines.append("Rangliste (gesperrte Namen ohne Medaille)")
    ranked = sorted(
        report["candidates"],
        key=lambda c: (
            -((c.get("score") or {}).get("total_points", 0) or 0),
            -((c.get("score") or {}).get("technical_points", 0) or 0),
            _ticker(c.get("symbol", "?")).upper(),
        ),
    )

    def _blocked(candidate: dict) -> bool:
        score = candidate.get("score") or {}
        if score.get("blocked"):
            return True
        label = str(score.get("label") or "")
        return label.startswith("SKIP (")

    eligible = [c for c in ranked if not _blocked(c) and (c.get("score") or {}).get("label") in {"STRONG_SETUP", "WATCH"}]
    blocked = [c for c in ranked if _blocked(c)]
    if not eligible:
        lines.append("• Keine handelbare Idee. Niemand hat die grüne Schwelle erreicht.")
    for i, c in enumerate(eligible[:10], 1):
        ticker = _display(c)
        score = c.get("score") or {}
        medal = {1: "1.", 2: "2.", 3: "3."}.get(i, f"{i}.")
        lines.append(f"• {medal} {ticker} — {_score_text(score)} — {_label_text(score)}")
    if blocked:
        names = ", ".join(_ticker(c.get("symbol", "?")) for c in blocked[:8])
        lines.append(f"Gesperrt, nicht gerankt: {names}")
    drops = report.get("drift_drops") or []
    if drops:
        lines.append("Seit der Vorauswahl raus (Kurs schon gelaufen oder scharf gefallen): " + ", ".join(drops))

    if empfehlung:
        lines.append("")
        lines.append("🎯 Meine Empfehlung")
        lines.append(empfehlung)

    text = "\n".join(lines).rstrip()
    # Standard: NICHT kuerzen. Hermes splittet lange Ausgaben selbst in so
    # viele Telegram-Nachrichten wie noetig. max_chars bleibt als optionaler
    # Hard-Cap fuer manuelle Laeufe.
    if not max_chars or len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n… (Report gekürzt, vollständig in data/reports/)"


__all__ = ["render_report"]