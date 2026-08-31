"""Stable non-TVRemix source adapters for the earnings monitor."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlencode
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

from .indicators import calculate_adx, calculate_ema, calculate_macd

FINNHUB_BASE = "https://finnhub.io/api/v1"
TWELVEDATA_BASE = "https://api.twelvedata.com"
TWELVEDATA_MIN_INTERVAL = 7.6  # 8 credits/minute => max. 1 request per 7.5s
TWELVEDATA_DAILY_CREDITS = 800
TWELVEDATA_STATE = os.path.expanduser("~/.cache/earnings-monitor/twelvedata_budget.json")
TWELVEDATA_LOCK = os.path.expanduser("~/.cache/earnings-monitor/twelvedata.lock")


def _reserve_twelvedata_credit() -> tuple[bool, str | None]:
    """Reserve one credit atomically across parallel shard processes."""
    os.makedirs(os.path.dirname(TWELVEDATA_STATE), exist_ok=True)
    os.makedirs(os.path.dirname(TWELVEDATA_LOCK), exist_ok=True)
    now = time.time()
    lock_handle = open(TWELVEDATA_LOCK, "a+", encoding="utf-8")
    try:
        if fcntl:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        last = 0.0
        try:
            lock_handle.seek(0)
            last = float(lock_handle.read().strip() or 0.0)
        except (ValueError, OSError):
            pass
        wait = TWELVEDATA_MIN_INTERVAL - (now - last)
        if wait > 0:
            time.sleep(wait)
            now = time.time()
        day = datetime.now(timezone.utc).date().isoformat()
        state = {"date": day, "credits": 0}
        try:
            with open(TWELVEDATA_STATE, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if loaded.get("date") == day:
                state = loaded
        except (OSError, ValueError, TypeError):
            pass
        if int(state.get("credits", 0)) >= TWELVEDATA_DAILY_CREDITS:
            return False, f"daily credit budget exhausted ({TWELVEDATA_DAILY_CREDITS})"
        state["credits"] = int(state.get("credits", 0)) + 1
        with open(TWELVEDATA_STATE, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        lock_handle.seek(0)
        lock_handle.truncate()
        lock_handle.write(str(now))
        lock_handle.flush()
        return True, None
    finally:
        if fcntl:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


def _ticker(symbol: str) -> str:
    return str(symbol).split(":")[-1].strip().upper()


# Finnhub's ``related`` field can contain the requested ticker even for
# roundup/market articles. Keep only titles with an explicit entity marker.
# These aliases cover the currently monitored small-cap test symbols; unknown
# symbols fail closed to the ticker token instead of accepting market noise.
_NEWS_ENTITY_ALIASES = {
    "BLRX": ("biolinerx", "bioline rx"),
    "CANG": ("cango",),
    "SAIC": ("science applications",),
}
_NEWS_ROUNDUP_MARKERS = (
    "stocks moving", "and 3 stocks", "stocks to watch", "nasdaq falls",
    "market update", "market roundup", "fear & greed index",
)


def _headline_matches_symbol(title: str, symbol: str) -> bool:
    normalized = str(title or "").lower()
    if any(marker in normalized for marker in _NEWS_ROUNDUP_MARKERS):
        return False
    ticker = _ticker(symbol).lower()
    if ticker and ticker in normalized:
        return True
    return any(alias in normalized for alias in _NEWS_ENTITY_ALIASES.get(_ticker(symbol), ()))


def _default_requester(url: str, *, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {"status": response.status, "body": response.read()}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read()}


def _decode(response: dict) -> tuple[int, object]:
    status = int(response.get("status", 0) or 0)
    body = response.get("body", b"")
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    try:
        return status, json.loads(body or "{}")
    except (TypeError, ValueError):
        return status, None


class FinnhubBase:
    def __init__(self, *, key: str | None = None, key_path: str | None = None,
                 requester: Callable | None = None, timeout: float = 10.0):
        self.key = key
        self.key_path = key_path
        self.requester = requester or _default_requester
        self.timeout = timeout

    def _token(self) -> str:
        if self.key is not None:
            return self.key.strip()
        if self.key_path:
            with open(self.key_path, encoding="utf-8") as handle:
                return handle.read().strip()
        return ""

    def _get(self, endpoint: str, params: dict) -> tuple[int, object]:
        token = self._token()
        if not token:
            return 0, None
        query = urlencode({**params, "token": token})
        try:
            return _decode(self.requester(
                f"{FINNHUB_BASE}/{endpoint}?{query}", headers={}, timeout=self.timeout
            ))
        except Exception:
            return 0, None


class FinnhubQuoteClient(FinnhubBase):
    def get(self, symbols: list[str]) -> dict:
        quotes = {}
        errors = {}
        for symbol in symbols:
            status, quote = self._get("quote", {"symbol": _ticker(symbol)})
            if status != 200 or not isinstance(quote, dict) or not isinstance(quote.get("c"), (int, float)) or quote["c"] <= 0:
                errors[symbol] = f"quote HTTP {status}" if status else "quote unavailable"
                continue
            pstatus, profile = self._get("stock/profile2", {"symbol": _ticker(symbol)})
            market_cap = None
            if pstatus == 200 and isinstance(profile, dict):
                # Finnhub's live stock/profile2 schema uses
                # marketCapitalization (million USD); older payloads used mktCap.
                raw_mcap = profile.get("marketCapitalization", profile.get("mktCap"))
                if isinstance(raw_mcap, (int, float)) and raw_mcap > 0:
                    market_cap = float(raw_mcap) * 1_000_000
            quotes[symbol] = {"price": float(quote["c"]), "market_cap": market_cap,
                              "source": "finnhub", "retrieved_at": datetime.now(timezone.utc).isoformat()}
            if market_cap is None:
                errors[symbol] = "market_cap unavailable"
        return {"status": "PASS" if quotes else "UNKNOWN", "quotes": quotes,
                **({"errors": errors} if errors else {})}


class FinnhubForecastClient(FinnhubBase):
    def get(self, symbol: str, *, price: float | None, as_of: str | None = None) -> dict:
        status_t, target = self._get("stock/price-target", {"symbol": _ticker(symbol)})
        status_r, recs = self._get("stock/recommendation", {"symbol": _ticker(symbol)})
        status_e, eps = self._get("stock/eps-estimate", {"symbol": _ticker(symbol), "freq": "quarterly"})
        forecast = {"target_recently_cut": None}
        missing = []
        errors = []
        if status_t == 200 and isinstance(target, dict) and isinstance(target.get("targetMean"), (int, float)):
            forecast["target_average"] = float(target["targetMean"])
            if isinstance(price, (int, float)) and price > 0:
                forecast["target_upside_pct"] = round((forecast["target_average"] / price - 1) * 100, 2)
            else:
                missing.append("target_upside_pct")
        else:
            missing.extend(["target_average", "target_upside_pct"])
        if status_e == 200 and isinstance(eps, dict) and isinstance(eps.get("data"), list) and eps["data"]:
            row = eps["data"][0]
            if isinstance(row, dict) and isinstance(row.get("epsAvg"), (int, float)):
                forecast["eps_estimate"] = float(row["epsAvg"])
            else:
                missing.append("eps_estimate")
        else:
            # Finnhub EPS estimates are Premium on the current Free tier.
            # The earnings calendar remains available and carries epsEstimate.
            day = (as_of or datetime.now(timezone.utc).isoformat())[:10]
            cal_status, calendar = self._get(
                "calendar/earnings", {"from": day, "to": day, "symbol": _ticker(symbol)}
            )
            rows = calendar.get("earningsCalendar", []) if isinstance(calendar, dict) else []
            row = rows[0] if rows and isinstance(rows[0], dict) else None
            if row and isinstance(row.get("epsEstimate"), (int, float)):
                forecast["eps_estimate"] = float(row["epsEstimate"])
                forecast["eps_source"] = "finnhub_earnings_calendar"
            else:
                missing.append("eps_estimate")
                errors.append(f"earnings-calendar HTTP {cal_status}")
        if status_r == 200 and isinstance(recs, list) and recs and isinstance(recs[0], dict):
            latest = recs[0]
            forecast["rating_buy"] = int(latest.get("buy", 0) or 0) + int(latest.get("strongBuy", 0) or 0)
            forecast["analyst_rating"] = "buy" if forecast["rating_buy"] else "neutral"
        else:
            missing.append("analyst_rating")
        forecast["missing"] = sorted(set(missing))
        errors.extend(
            message for message in (
                f"price-target HTTP {status_t}" if status_t != 200 else None,
                f"eps-estimate HTTP {status_e}" if status_e != 200 else None,
                f"recommendation HTTP {status_r}" if status_r != 200 else None,
            ) if message
        )
        return {"status": "PASS" if not missing else ("PARTIAL" if forecast else "UNKNOWN"),
                "forecast": forecast, "error": "; ".join(errors + forecast["missing"]) or None}


class FinnhubNewsClient(FinnhubBase):
    def __init__(self, *, fallback_requester: Callable | None = None, **kwargs):
        super().__init__(**kwargs)
        self.fallback_requester = fallback_requester or _default_requester

    def _yahoo_fallback(self, symbol: str, *, as_of: str) -> dict:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={_ticker(symbol)}&region=US&lang=en-US"
        try:
            end = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        except ValueError:
            end = datetime.now(timezone.utc)
        cutoff = end - timedelta(days=7)
        try:
            response = self.fallback_requester(
                url, headers={"User-Agent": "earnings-monitor/1.0"}, timeout=self.timeout
            )
            status = int(response.get("status", 0) or 0)
            if status != 200:
                return {"status": "UNKNOWN", "headlines": [], "negative_news": None,
                        "error": f"yahoo-rss HTTP {status}"}
            raw = response.get("body", b"")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            root = ET.fromstring(raw)
            headlines = []
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                if title:
                    published = (item.findtext("pubDate") or "").strip() or None
                    if published:
                        try:
                            published_dt = parsedate_to_datetime(published).astimezone(timezone.utc)
                            if not cutoff <= published_dt <= end:
                                continue
                        except (TypeError, ValueError, OverflowError):
                            continue
                    headlines.append({
                        "headline": title,
                        "published": published,
                        "link": (item.findtext("link") or "").strip() or None,
                    })
            if not headlines:
                return {"status": "UNKNOWN", "headlines": [], "negative_news": None,
                        "error": "yahoo-rss returned no headlines"}
            negative_terms = ("miss", "downgrade", "lawsuit", "recall", "bankruptcy", "dilution", "fraud", "warns")
            negative = any(any(term in h["headline"].lower() for term in negative_terms) for h in headlines)
            return {"status": "PASS", "source": "yahoo_rss", "headlines": headlines[:10],
                    "negative_news": negative}
        except Exception as exc:
            return {"status": "UNKNOWN", "headlines": [], "negative_news": None,
                    "error": f"yahoo-rss {type(exc).__name__}"}

    def get(self, symbol: str, *, as_of: str) -> dict:
        try:
            end = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        except ValueError:
            end = datetime.now(timezone.utc)
        start = (end - timedelta(days=7)).date().isoformat()
        status, raw = self._get("company-news", {"symbol": _ticker(symbol), "from": start, "to": end.date().isoformat()})
        if status != 200 or not isinstance(raw, list):
            fallback = self._yahoo_fallback(symbol, as_of=as_of)
            if fallback.get("status") == "PASS":
                fallback["fallback_from"] = f"finnhub_company_news_http_{status or 'unavailable'}"
                return fallback
            return {"status": "UNKNOWN", "headlines": [], "negative_news": None,
                    "error": (f"company-news HTTP {status}" if status else "company-news unavailable")
                              + "; " + fallback.get("error", "yahoo-rss unavailable")}
        ticker = _ticker(symbol)
        headlines = []
        for item in raw:
            if not isinstance(item, dict) or not item.get("headline"):
                continue
            # Finnhub can return a market/article cluster for company-news.
            # When ``related`` is explicit, keep only articles that name this
            # ticker; never silently attribute another symbol's article here.
            related = str(item.get("related") or "").upper()
            related_symbols = {part.strip() for part in related.replace(";", ",").split(",") if part.strip()}
            if related_symbols and ticker not in related_symbols:
                continue
            if not _headline_matches_symbol(item.get("headline", ""), symbol):
                continue
            headlines.append({"headline": item.get("headline", ""),
                              "published": item.get("datetime"),
                              "link": item.get("url"),
                              "related": item.get("related") or None})
        negative_terms = ("miss", "downgrade", "lawsuit", "recall", "bankruptcy", "dilution", "fraud", "warns")
        negative = any(any(term in h["headline"].lower() for term in negative_terms) for h in headlines)
        if not headlines:
            fallback = self._yahoo_fallback(symbol, as_of=as_of)
            if fallback.get("status") == "PASS":
                fallback["fallback_from"] = "finnhub_company_news_empty"
                return fallback
            return {"status": "UNKNOWN", "headlines": [], "negative_news": None,
                    "error": "company-news empty; " + fallback.get("error", "yahoo-rss unavailable")}
        return {"status": "PASS", "headlines": headlines[:10], "negative_news": negative}


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(x, 0.0) for x in changes[-period:]]
    losses = [max(-x, 0.0) for x in changes[-period:]]
    if sum(losses) == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + sum(gains) / sum(losses)))


class TwelveDataTechnicalClient:
    def __init__(self, *, key: str | None = None, key_path: str | None = None,
                 requester: Callable | None = None, timeout: float = 10.0, outputsize: int = 60,
                 rate_limit: bool | None = None):
        self.key, self.key_path = key, key_path
        self.requester, self.timeout, self.outputsize = requester or _default_requester, timeout, outputsize
        # Custom requesters are normally offline test doubles; production HTTP
        # uses the process-wide limiter, including parallel shard processes.
        self.rate_limit = requester is None if rate_limit is None else rate_limit
        self.last_error: str | None = None

    def _get_bars(self, symbol: str, interval: str) -> list[dict] | None:
        key = self.key
        if key is None and self.key_path:
            with open(self.key_path, encoding="utf-8") as handle:
                key = handle.read().strip()
        if not key:
            self.last_error = "TWELVEDATA_API_KEY missing"
            return None
        if self.rate_limit:
            allowed, reason = _reserve_twelvedata_credit()
            if not allowed:
                self.last_error = reason
                return None
        query = urlencode({"symbol": _ticker(symbol), "interval": interval, "outputsize": self.outputsize, "apikey": key, "order": "ASC"})
        try:
            status, data = _decode(self.requester(f"{TWELVEDATA_BASE}/time_series?{query}", headers={}, timeout=self.timeout))
        except Exception as exc:
            self.last_error = f"request failed: {type(exc).__name__}"
            return None
        if status != 200 or not isinstance(data, dict) or not isinstance(data.get("values"), list):
            self.last_error = f"HTTP {status} or invalid time_series payload"
            return None
        bars = []
        for row in data["values"]:
            try:
                bars.append({"o": float(row["open"]), "h": float(row["high"]), "l": float(row["low"]), "c": float(row["close"]), "v": float(row.get("volume", 0))})
            except (KeyError, TypeError, ValueError):
                continue
        if not bars:
            self.last_error = "empty or invalid time_series values"
        return bars or None

    def get(self, symbol: str) -> dict:
        bars_1d, bars_4h = self._get_bars(symbol, "1day"), self._get_bars(symbol, "4h")
        if not bars_1d or not bars_4h:
            return {"status": "UNKNOWN", "values": {}, "unknown": ["ohlcv_1d", "ohlcv_4h"],
                    "error": self.last_error or "twelve-data OHLCV unavailable"}
        c1, c4 = [b["c"] for b in bars_1d], [b["c"] for b in bars_4h]
        macd = calculate_macd(c1)
        values = {"price_1d": c1[-1], "price_4h": c4[-1], "ema20_1d": calculate_ema(c1, 20)[-1],
                  "ema20_4h": calculate_ema(c4, 20)[-1], "ema50_1d": calculate_ema(c1, 50)[-1],
                  "rsi_1d": _rsi(c1), "adx_1d": calculate_adx(bars_1d, 14),
                  "macd_1d": macd["line"] if macd else None,
                  "macd_signal_1d": macd["signal"] if macd else None,
                  "macd_histogram_1d": macd["histogram"] if macd else None}
        unknown = [key for key, value in values.items() if value is None]
        return {"status": "PASS" if not unknown else "PARTIAL", "values": values, "unknown": unknown,
                "source": "twelve_data"}


class StaticCalendarClient:
    """Calendar adapter for an already-discovered symbol list; timing stays explicit UNKNOWN."""
    def get(self, *, symbols, date_from=None, date_to=None):
        return {"status": "PASS", "events": [{"symbol": symbol, "timing": "UNKNOWN"} for symbol in symbols]}
