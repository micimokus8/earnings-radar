"""Wire real clients into the pipeline (network boundary lives here only)."""

from __future__ import annotations

import time
from pathlib import Path

from earnings_monitor.pipeline import EarningsPipeline
from earnings_monitor.alternative_sources import (
    FinnhubForecastClient,
    FinnhubNewsClient,
    FinnhubQuoteClient,
    StaticCalendarClient,
    TwelveDataTechnicalClient,
)
from earnings_monitor.technicals_normalizer import normalize_technicals_for_score
from earnings_monitor.finnhub_outstanding_client import FinnhubOutstandingClient
from earnings_monitor.finnhub_short_interest_fallback import FinnhubShortInterestFallback
from earnings_monitor.nasdaq_short_interest_client import NasdaqShortInterestClient
from earnings_monitor.sec_http import SecHttpClient
from earnings_monitor.sec_orchestration import (
    make_dilution_lookup,
    make_insider_lookup,
)
from earnings_monitor.screener_discovery import parse_screener_rows
from earnings_monitor.short_interest_provider import ShortInterestProvider
from earnings_monitor.tvremix_calendar_client import TvremixCalendarClient
from earnings_monitor.tvremix_forecast_client import TvremixForecastClient
from earnings_monitor.tvremix_http import request_json
from earnings_monitor.tvremix_mcp_session import TvremixMcpSession
from earnings_monitor.tvremix_news_client import TvremixNewsClient
from earnings_monitor.tvremix_quotes_client import TvremixQuotesClient
from earnings_monitor.tvremix_technicals_client import TvremixTechnicalsClient
from earnings_monitor.symbol_resolution import TvremixSymbolResolver

DEFAULT_TVREMIX_URL = "https://tvremix.xyz/api/mcp/v1"


class RetryWrapper:
    """Thin retry wrapper for sources WITHOUT their own retry logic.

    Nasdaq SI, Finnhub, SEC etc. have zero internal retry — a single
    network hiccup kills them. This wrapper adds bounded retries (2 max)
    with exponential backoff.

    NOT for tvremix-based sources — they already retry 3x internally
    via ``tvremix_http.request_json``.
    """

    def __init__(self, inner, *, retries: int = 2, backoff: float = 0.5):
        self.inner = inner
        self.retries = retries
        self.backoff = backoff

    def get(self, *args, **kwargs):
        last_result = None
        for attempt in range(self.retries + 1):
            try:
                result = self.inner.get(*args, **kwargs)
            except Exception as exc:
                last_result = {"status": "UNKNOWN", "error": type(exc).__name__}
            else:
                if isinstance(result, dict) and result.get("status") not in ("UNKNOWN", None):
                    return result
                last_result = result if isinstance(result, dict) else {"status": "UNKNOWN"}
            if attempt < self.retries:
                time.sleep(self.backoff * (2 ** attempt))
        return last_result


def load_optional_text(path) -> str | None:
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def build_tvremix_session(*, secret_path: str, url: str = DEFAULT_TVREMIX_URL,
                          timeout: float = 20.0) -> TvremixMcpSession:
    token = Path(secret_path).read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("TVRemix secret file is empty")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    return TvremixMcpSession(url=url, headers=headers,
                             requester=request_json, timeout=timeout)


class TechnicalScoreAdapter:
    """Map raw TVRemix technicals/OHLCV to the score 'values' block."""

    def __init__(self, inner):
        self.inner = inner

    def get(self, symbol: str) -> dict:
        return normalize_technicals_for_score(self.inner.get(symbol))


class _PrimaryFallback:
    """Use TVRemix first and consult a secondary source when needed."""

    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback


class QuotePrimaryFallback(_PrimaryFallback):
    def get(self, symbols):
        primary = self.primary.get(symbols)
        quotes = dict(primary.get("quotes", {}) if isinstance(primary, dict) else {})
        secondary = self.fallback.get(symbols)
        for symbol, row in (secondary.get("quotes", {}) if isinstance(secondary, dict) else {}).items():
            quotes.setdefault(symbol, row)
        return {"status": "PASS" if quotes else "UNKNOWN", "quotes": quotes}


class ForecastPrimaryFallback(_PrimaryFallback):
    def get(self, symbol: str, *, price, as_of=None):
        primary = self.primary.get(symbol, price=price)
        secondary = self.fallback.get(symbol, price=price, as_of=as_of)
        first = primary.get("forecast") if isinstance(primary, dict) else {}
        second = secondary.get("forecast") if isinstance(secondary, dict) else {}
        first = first if isinstance(first, dict) else {}
        second = second if isinstance(second, dict) else {}
        merged = dict(first)
        for key, value in second.items():
            if key not in merged or merged[key] is None:
                merged[key] = value
        # Keep fallback provenance only when the fallback actually supplied the
        # field; otherwise the report must not call a TVRemix EPS "Kalender".
        if first.get("eps_estimate") is not None:
            merged.pop("eps_source", None)
        merged["missing"] = sorted(key for key in set(first.get("missing", [])) | set(second.get("missing", [])) if merged.get(key) is None)
        return {"status": "PASS" if not merged["missing"] else "PARTIAL", "forecast": merged,
                "sources": {"primary": "tvremix", "fallback": "finnhub"}}


class NewsPrimaryFallback(_PrimaryFallback):
    def get(self, symbol: str, *, as_of):
        primary = self.primary.get(symbol, as_of=as_of)
        if isinstance(primary, dict) and primary.get("headlines"):
            return primary
        secondary = self.fallback.get(symbol, as_of=as_of)
        return secondary if isinstance(secondary, dict) and secondary.get("headlines") else primary


class TechnicalPrimaryFallback(_PrimaryFallback):
    def get(self, symbol: str):
        primary = self.primary.get(symbol)
        if isinstance(primary, dict) and primary.get("status") in {"PASS", "PARTIAL"}:
            return primary
        return self.fallback.get(symbol)


class ScreenerDiscoveryClient:
    """Market-wide earnings discovery via date-sorted screener rows."""

    _COLUMNS = ["name", "earnings_release_next_date"]

    def __init__(self, session, *, limit: int = 1000,
                 exclude_prefixes: tuple[str, ...] = (),
                 min_market_cap: float | None = None):
        self.session = session
        self.limit = limit
        self.exclude_prefixes = tuple(exclude_prefixes)
        self.min_market_cap = min_market_cap

    def get(self, target_date: str) -> list[str]:
        result = self.session.call_tool("run_screener", {
            "sort_by": "earnings_release_next_date",
            "sort_order": "asc",
            "limit": self.limit,
            "columns": ["name", "earnings_release_next_date",
                         "market_cap_basic"],
        })
        if result.get("status") != "PASS":
            return []
        response = result.get("response") or {}
        content = ((response.get("result") or {}).get("content") or [{}])[0]
        try:
            import json as _json
            payload = _json.loads(content.get("text", "{}"))
        except Exception:
            return []
        rows = ((payload.get("data") or {}).get("results")) or []
        symbols = parse_screener_rows(rows, target_date=target_date)
        mcap_by_symbol = {
            row.get("symbol"): row.get("market_cap_basic") or 0
            for row in rows if isinstance(row, dict)
        }
        filtered = []
        for symbol in symbols:
            if any(symbol.startswith(prefix) for prefix in self.exclude_prefixes):
                continue
            if self.min_market_cap is not None and \
                    mcap_by_symbol.get(symbol, 0) < self.min_market_cap:
                continue
            filtered.append(symbol)
        return filtered


def build_default_pipeline(
    *,
    tvremix_secret_path: str,
    finnhub_key_path: str,
    twelvedata_key_path: str = "TwelveData Key.txt",
    sec_user_agent_path: str | None = None,
    url: str = DEFAULT_TVREMIX_URL,
    ohlcv_count: int = 300,
    timeout: float = 20.0,
    throttle_seconds: float = 0.0,
) -> EarningsPipeline:
    try:
        finnhub_key = Path(finnhub_key_path).read_text(encoding="utf-8").strip()
    except OSError:
        finnhub_key = ""
    # TVRemix is the primary enrichment source; free providers fill gaps.
    session = build_tvremix_session(secret_path=tvremix_secret_path, url=url, timeout=timeout)
    resolver = TvremixSymbolResolver(session)
    tv_technicals = TechnicalScoreAdapter(
        TvremixTechnicalsClient(session, ohlcv_count=ohlcv_count)
    )
    technicals = TechnicalPrimaryFallback(
        tv_technicals,
        TwelveDataTechnicalClient(
            key_path=twelvedata_key_path, timeout=timeout, outputsize=max(ohlcv_count, 60)
        ),
    )
    finnhub_quotes = FinnhubQuoteClient(key=finnhub_key, timeout=timeout)
    finnhub_forecasts = FinnhubForecastClient(key=finnhub_key, timeout=timeout)
    finnhub_news = FinnhubNewsClient(key=finnhub_key, timeout=timeout)
    short_interest = ShortInterestProvider(
        nasdaq=RetryWrapper(NasdaqShortInterestClient(timeout=timeout), retries=2, backoff=0.5),
        outstanding=RetryWrapper(FinnhubOutstandingClient(
            key_path=finnhub_key_path, timeout=timeout
        ), retries=1, backoff=0.5),
        finnhub_short=RetryWrapper(FinnhubShortInterestFallback(
            key_path=finnhub_key_path, timeout=timeout
        ), retries=1, backoff=0.5),
    )

    user_agent = load_optional_text(sec_user_agent_path) if sec_user_agent_path else None
    insider = dilution = None
    if user_agent:
        sec_client = SecHttpClient(user_agent=user_agent, timeout=timeout)
        insider = make_insider_lookup(sec_client)
        dilution = make_dilution_lookup(sec_client)

    return EarningsPipeline(
        calendar=StaticCalendarClient(),
        quotes=QuotePrimaryFallback(TvremixQuotesClient(session), finnhub_quotes),
        forecasts=ForecastPrimaryFallback(TvremixForecastClient(session, url), finnhub_forecasts),
        technicals=technicals,
        news=NewsPrimaryFallback(TvremixNewsClient(session), finnhub_news),
        short_interest=short_interest,
        insider=insider,
        dilution=dilution,
        throttle_seconds=throttle_seconds,
        symbol_timeout=90.0,
        symbol_resolver=resolver,
    )


__all__ = [
    "DEFAULT_TVREMIX_URL",
    "load_optional_text",
    "build_tvremix_session",
    "TechnicalScoreAdapter",
    "RetryWrapper",
    "build_default_pipeline",
]

      
