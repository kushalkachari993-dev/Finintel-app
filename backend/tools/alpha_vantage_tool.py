import logging
from datetime import datetime
from datetime import timezone

import requests

from backend.config.settings import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_BASE_URL,
    ALPHA_VANTAGE_CACHE_SECONDS,
    EXTERNAL_CALL_TIMEOUT_SECONDS,
)
from backend.utils.simple_cache import build_cache


logger = logging.getLogger(__name__)


class AlphaVantageTool:
    """Structured end-of-day quote fallback for supported global equities."""

    quote_cache = build_cache(
        ttl_seconds=ALPHA_VANTAGE_CACHE_SECONDS,
        namespace="alpha_vantage_quote",
    )
    search_cache = build_cache(
        ttl_seconds=86400,
        namespace="alpha_vantage_symbol_search",
    )

    def __init__(
        self,
        api_key: str | None = ALPHA_VANTAGE_API_KEY,
        base_url: str = ALPHA_VANTAGE_BASE_URL,
    ):
        self.api_key = api_key
        self.base_url = base_url

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def yahoo_to_alpha_symbol(ticker: str) -> tuple[str, str | None, str]:
        normalized = str(ticker or "").strip().upper()

        if normalized.endswith(".NS"):
            return f"{normalized.removesuffix('.NS')}.BSE", "BSE", "INR"

        if normalized.endswith(".BO"):
            return f"{normalized.removesuffix('.BO')}.BSE", "BSE", "INR"

        return normalized, None, "USD"

    def _request(self, function: str, **params) -> dict | None:
        if not self.is_configured():
            return None

        request_params = {
            "function": function,
            "apikey": self.api_key,
            **params,
        }

        try:
            response = requests.get(
                self.base_url,
                params=request_params,
                timeout=EXTERNAL_CALL_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception(
                "alpha_vantage_request_failed function=%s",
                function,
            )
            return None

        if not response.ok:
            logger.warning(
                "alpha_vantage_http_error function=%s status_code=%s",
                function,
                response.status_code,
            )
            return None

        try:
            payload = response.json()
        except ValueError:
            logger.warning(
                "alpha_vantage_invalid_json function=%s",
                function,
            )
            return None

        if not isinstance(payload, dict):
            return None

        provider_message = (
            payload.get("Error Message")
            or payload.get("Note")
            or payload.get("Information")
        )

        if provider_message:
            logger.warning(
                "alpha_vantage_provider_message function=%s message=%r",
                function,
                provider_message,
            )
            return None

        return payload

    @staticmethod
    def _to_float(value):
        if value in (None, ""):
            return None

        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    def symbol_search(self, query: str) -> list[dict]:
        normalized_query = str(query or "").strip()

        if not normalized_query or not self.is_configured():
            return []

        cache_key = normalized_query.lower()
        cached = self.search_cache.get(cache_key)

        if cached is not None:
            return cached

        payload = self._request(
            "SYMBOL_SEARCH",
            keywords=normalized_query,
        )
        matches = payload.get("bestMatches", []) if payload else []

        if not isinstance(matches, list):
            matches = []

        return self.search_cache.set(cache_key, matches)

    def get_quote_data(
        self,
        ticker: str,
        company_name: str | None = None,
    ) -> dict | None:
        symbol, exchange, currency = self.yahoo_to_alpha_symbol(ticker)

        if not symbol or not self.is_configured():
            return None

        cache_key = symbol
        cached = self.quote_cache.get(cache_key)

        if cached is not None:
            logger.info(
                "alpha_vantage_quote_cache_hit ticker=%s",
                ticker,
            )
            return cached

        quote_payload = self._request(
            "GLOBAL_QUOTE",
            symbol=symbol,
        )
        result = self._build_from_quote(
            payload=quote_payload,
            ticker=ticker,
            symbol=symbol,
            company_name=company_name,
            exchange=exchange,
            currency=currency,
        )

        if not result:
            daily_payload = self._request(
                "TIME_SERIES_DAILY",
                symbol=symbol,
                outputsize="compact",
            )
            result = self._build_from_daily(
                payload=daily_payload,
                ticker=ticker,
                symbol=symbol,
                company_name=company_name,
                exchange=exchange,
                currency=currency,
            )

        if not result:
            return self.quote_cache.set(
                cache_key,
                {"error": "Alpha Vantage did not return usable stock data."},
            )

        logger.info(
            "alpha_vantage_price_success ticker=%s symbol=%s date=%s",
            ticker,
            symbol,
            result.get("price_date"),
        )
        return self.quote_cache.set(cache_key, result)

    def _build_from_quote(
        self,
        payload: dict | None,
        ticker: str,
        symbol: str,
        company_name: str | None,
        exchange: str | None,
        currency: str,
    ) -> dict | None:
        quote = payload.get("Global Quote") if payload else None

        if not isinstance(quote, dict):
            return None

        price = self._to_float(quote.get("05. price"))

        if price is None or price <= 0:
            return None

        return self._stock_data_result(
            ticker=ticker,
            symbol=symbol,
            company_name=company_name,
            exchange=exchange,
            currency=currency,
            current_price=price,
            price_date=quote.get("07. latest trading day"),
            previous_close=self._to_float(quote.get("08. previous close")),
            day_open=self._to_float(quote.get("02. open")),
            day_high=self._to_float(quote.get("03. high")),
            day_low=self._to_float(quote.get("04. low")),
            volume=self._to_float(quote.get("06. volume")),
            change=self._to_float(quote.get("09. change")),
            percent_change=self._to_float(
                str(quote.get("10. change percent", "")).removesuffix("%")
            ),
            source_function="GLOBAL_QUOTE",
            data_quality_score=0.35,
        )

    def _build_from_daily(
        self,
        payload: dict | None,
        ticker: str,
        symbol: str,
        company_name: str | None,
        exchange: str | None,
        currency: str,
    ) -> dict | None:
        series = payload.get("Time Series (Daily)") if payload else None

        if not isinstance(series, dict) or not series:
            return None

        price_date = max(series)
        latest = series.get(price_date)

        if not isinstance(latest, dict):
            return None

        price = self._to_float(latest.get("4. close"))

        if price is None or price <= 0:
            return None

        return self._stock_data_result(
            ticker=ticker,
            symbol=symbol,
            company_name=company_name,
            exchange=exchange,
            currency=currency,
            current_price=price,
            price_date=price_date,
            day_open=self._to_float(latest.get("1. open")),
            day_high=self._to_float(latest.get("2. high")),
            day_low=self._to_float(latest.get("3. low")),
            volume=self._to_float(latest.get("5. volume")),
            source_function="TIME_SERIES_DAILY",
            data_quality_score=0.3,
        )

    def _stock_data_result(
        self,
        ticker: str,
        symbol: str,
        company_name: str | None,
        exchange: str | None,
        currency: str,
        current_price: float,
        price_date: str | None,
        source_function: str,
        previous_close: float | None = None,
        day_open: float | None = None,
        day_high: float | None = None,
        day_low: float | None = None,
        volume: float | None = None,
        change: float | None = None,
        percent_change: float | None = None,
        data_quality_score: float = 0.3,
    ) -> dict:
        return {
            "company_name": company_name or symbol or ticker,
            "sector": None,
            "current_price": current_price,
            "market_cap": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "roe": None,
            "roe_raw": None,
            "profit_margin": None,
            "profit_margin_raw": None,
            "operating_margin": None,
            "operating_margin_raw": None,
            "revenue_growth": None,
            "revenue_growth_raw": None,
            "debt_to_equity": None,
            "debt_to_equity_raw": None,
            "dividend_yield": None,
            "dividend_yield_raw": None,
            "currency": currency,
            "exchange": exchange,
            "alpha_vantage_symbol": symbol,
            "previous_close": previous_close,
            "day_open": day_open,
            "day_high": day_high,
            "day_low": day_low,
            "volume": volume,
            "change": change,
            "percent_change": percent_change,
            "provider": "alpha_vantage",
            "price_freshness": "end_of_day",
            "price_date": price_date,
            "source_url": (
                f"https://www.alphavantage.co/query?function={source_function}"
                f"&symbol={symbol}"
            ),
            "data_quality_score": data_quality_score,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
