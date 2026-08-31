"""Build one auditable normalized earnings candidate."""

from __future__ import annotations

from earnings_monitor.scoring import score_candidate


def _status(value):
    return value.get("status") if isinstance(value, dict) else "UNKNOWN"


def build_candidate(
    *,
    symbol: str,
    as_of: str,
    calendar: dict | None = None,
    quote: dict | None = None,
    forecast: dict | None = None,
    technicals: dict | None = None,
    news: dict | None = None,
    short_interest: dict | None = None,
    insider_status: str = "UNKNOWN",
    dilution_status: str = "UNKNOWN",
) -> dict:
    calendar = calendar or {}
    quote = quote or {}
    forecast = forecast or {}
    technicals = technicals or {}
    news = news or {}
    short_interest = short_interest or {}

    quote_map = quote.get("quotes", {}) if isinstance(quote, dict) else {}
    quote_row = quote_map.get(symbol, {}) if isinstance(quote_map, dict) else {}
    if not isinstance(quote_row, dict):
        quote_row = {}
    forecast_row = forecast.get("forecast") if isinstance(forecast, dict) else None
    if not isinstance(forecast_row, dict):
        forecast_row = {}
    technical_values = technicals.get("values", {}) if isinstance(technicals, dict) else {}
    if not isinstance(technical_values, dict):
        technical_values = {}

    values = {
        "price": quote_row.get("price"),
        "market_cap": quote_row.get("market_cap"),
        "eps_estimate": forecast_row.get("eps_estimate"),
        "analyst_rating": forecast_row.get("analyst_rating"),
        "target_average": forecast_row.get("target_average"),
        "target_upside_pct": forecast_row.get("target_upside_pct"),
        "target_recently_cut": forecast_row.get("target_recently_cut"),
        "short_pct_outstanding": short_interest.get("short_pct_outstanding"),
        "days_to_cover": short_interest.get("days_to_cover"),
        "short_interest_supported": not short_interest.get("exchange_unsupported", False),
        "ohlcv_1d": technical_values.get("price_1d"),
        "news_status": _status(news),
        "negative_news": news.get("negative_news"),
        "insider_status": insider_status,
        "dilution_status": dilution_status,
    }
    values.update({
        key: technical_values.get(key)
        for key in (
            "price_1d", "price_4h", "ema20_1d", "ema20_4h", "ema50_1d",
            "rsi_1d", "adx_1d", "macd_1d", "macd_signal_1d", "macd_histogram_1d",
        )
    })
    # Persist real provider headlines so telegram + LLM can display them.
    headlines = news.get("headlines", []) if isinstance(news, dict) else []
    headlines = [item for item in headlines if isinstance(item, dict) and item.get("headline")]
    top_headline = headlines[0].get("headline") if headlines else None

    score = score_candidate(values)
    missing = list(score.get("missing", []))
    if not symbol:
        missing.insert(0, "symbol")
    status = "INCOMPLETE" if missing else score["state"]
    if status == "COMPLETE":
        status = "PASS"

    return {
        "symbol": symbol,
        "as_of": as_of,
        "status": status,
        "missing": missing,
        "values": values,
        "sources": {
            "calendar": calendar,
            "quote": quote,
            "forecast": forecast,
            "technicals": technicals,
            "news": news,
            "short_interest": short_interest,
            "insider_status": insider_status,
            "dilution_status": dilution_status,
        },
        "score": score,
        "headlines": headlines[:10],
        "top_headline": top_headline,
        "top_headline_url": headlines[0].get("link") if headlines else None,
        "news_source": news.get("source") if isinstance(news, dict) else None,
    }


__all__ = ["build_candidate"]

        
      
  