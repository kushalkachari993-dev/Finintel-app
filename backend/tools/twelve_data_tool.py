import logging
from datetime import datetime
from datetime import timezone

import requests

from backend.config.settings import (
    EXTERNAL_CALL_TIMEOUT_SECONDS,
    STOCK_DATA_CACHE_SECONDS,
    TWELVE_DATA_API_KEY,
    TWELVE_DATA_BASE_URL,
)
from backend.utils.simple_cache import build_cache


logger = logging.getLogger(__name__)


class TwelveDataTool:
    """Thin Twelve Data REST client for market data provider fallback chains."""

    quote_cache = build_cache(
        ttl_seconds=STOCK_DATA_CACHE_SECONDS,
        namespace="twelve_data_quote",
    )
    search_cache = build_cache(
        ttl_seconds=STOCK_DATA_CACHE_SECONDS,
        namespace="twelve_data_symbol_search",
    )

    def __init__(
        self,
        api_key: str | None = TWELVE_DATA_API_KEY,
        base_url: str = TWELVE_DATA_BASE_URL,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def yahoo_to_twelve_symbol(self, ticker: str) -> tuple[str, str | None]:
        normalized = str(ticker or "").strip().upper()

        if normalized.endswith(".NS"):
            return normalized.removesuffix(".NS"), "NSE"

        if normalized.endswith(".BO"):
            return normalized.removesuffix(".BO"), "BSE"

        return normalized, None

    def _request(
        self,
        endpoint: str,
        params: dict,
    ) -> dict | None:
        if not self.is_configured():
            return None

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_params = {
            **params,
            "apikey": self.api_key,
            "format": "JSON",
        }

        try:
            response = requests.get(
                url,
                params=request_params,
                timeout=EXTERNAL_CALL_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception(
                "twelve_data_request_failed endpoint=%s params=%s",
                endpoint,
                {key: value for key, value in params.items() if key != "apikey"},
            )
            return None

        if not response.ok:
            logger.warning(
                "twelve_data_http_error endpoint=%s status_code=%s params=%s",
                endpoint,
                response.status_code,
                {key: value for key, value in params.items() if key != "apikey"},
            )
            return None

        try:
            payload = response.json()
        except ValueError:
            logger.warning(
                "twelve_data_invalid_json endpoint=%s params=%s",
                endpoint,
                {key: value for key, value in params.items() if key != "apikey"},
            )
            return None

        if isinstance(payload, dict) and payload.get("status") == "error":
            logger.warning(
                "twelve_data_error endpoint=%s code=%r message=%r",
                endpoint,
                payload.get("code"),
                payload.get("message"),
            )
            return None

        if not isinstance(payload, dict):
            return None

        return payload

    @staticmethod
    def _to_float(value):
        if value in (None, ""):
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def symbol_search(
        self,
        query: str,
    ) -> list[dict]:
        normalized_query = str(query or "").strip()

        if not normalized_query or not self.is_configured():
            return []

        cache_key = normalized_query.lower()
        cached = self.search_cache.get(cache_key)

        if cached is not None:
            logger.info(
                "twelve_data_symbol_search_cache_hit query=%r",
                query,
            )
            return cached

        payload = self._request(
            "symbol_search",
            {
                "symbol": normalized_query,
                "country": "India",
            },
        )

        if not payload:
            return self.search_cache.set(cache_key, [])

        data = payload.get("data")

        if not isinstance(data, list):
            data = []

        return self.search_cache.set(cache_key, data)

    def select_best_symbol(
        self,
        candidates: list[dict],
    ) -> dict | None:
        if not candidates:
            return None

        ranked_exchanges = {
            "NSE": 0,
            "BSE": 1,
        }

        sorted_candidates = sorted(
            candidates,
            key=lambda item: (
                ranked_exchanges.get(
                    str(item.get("exchange", "")).upper(),
                    9,
                ),
                0
                if str(item.get("instrument_type", "")).lower()
                in {"common stock", "equity"}
                else 1,
            ),
        )

        candidate = sorted_candidates[0]
        symbol = candidate.get("symbol")
        exchange = candidate.get("exchange")

        if not symbol:
            return None

        yahoo_ticker = str(symbol).upper()

        if str(exchange).upper() == "NSE":
            yahoo_ticker = f"{yahoo_ticker}.NS"
        elif str(exchange).upper() == "BSE":
            yahoo_ticker = f"{yahoo_ticker}.BO"

        return {
            "ticker": yahoo_ticker,
            "company_name": (
                candidate.get("instrument_name")
                or candidate.get("name")
                or symbol
            ),
            "exchange": exchange or "UNKNOWN",
            "confidence": 0.82,
            "provider": "twelve_data",
        }

    def resolve_symbol(
        self,
        company_name: str,
    ) -> dict | None:
        return self.select_best_symbol(
            self.symbol_search(company_name)
        )

    def get_quote_data(
        self,
        ticker: str,
    ) -> dict | None:
        symbol, exchange = self.yahoo_to_twelve_symbol(ticker)

        if not symbol or not self.is_configured():
            return None

        cache_key = (
            symbol,
            exchange,
        )
        cached = self.quote_cache.get(cache_key)

        if cached is not None:
            logger.info(
                "twelve_data_quote_cache_hit ticker=%s",
                ticker,
            )
            return cached

        param_variants = self.market_data_param_variants(
            symbol=symbol,
            exchange=exchange,
        )

        quote = self._request(
            "quote",
            param_variants[0],
        )

        if not quote:
            quote = self._first_successful_request(
                "quote",
                param_variants[1:],
            )

        price = None
        eod = None

        if not quote:
            price = self._first_successful_request(
                "price",
                param_variants,
            )

        if not quote and not price:
            eod = self._first_successful_request(
                "eod",
                param_variants,
            )

        result = self._build_stock_data(
            ticker=ticker,
            quote=quote,
            price=price,
            eod=eod,
        )

        if not result:
            return self.quote_cache.set(
                cache_key,
                {
                    "error": "Twelve Data did not return usable stock data."
                },
            )

        return self.quote_cache.set(
            cache_key,
            result,
        )

    def _first_successful_request(
        self,
        endpoint: str,
        param_variants: list[dict],
    ) -> dict | None:
        for params in param_variants:
            payload = self._request(
                endpoint,
                params,
            )

            if payload:
                return payload

        return None

    def market_data_param_variants(
        self,
        symbol: str,
        exchange: str | None,
    ) -> list[dict]:
        base_symbol = str(symbol or "").strip().upper()
        exchange_name = str(exchange or "").strip().upper()
        mic_code = {
            "NSE": "XNSE",
            "BSE": "XBOM",
        }.get(exchange_name)

        if not base_symbol:
            return []

        variants = []

        if exchange_name:
            variants.append(
                {
                    "symbol": f"{base_symbol}:{exchange_name}",
                }
            )
            if mic_code:
                variants.append(
                    {
                        "symbol": base_symbol,
                        "mic_code": mic_code,
                    }
                )
            variants.append(
                {
                    "symbol": base_symbol,
                    "exchange": exchange_name,
                }
            )
            variants.append(
                {
                    "symbol": base_symbol,
                    "country": "India",
                }
            )

        variants.append(
            {
                "symbol": base_symbol,
            }
        )

        unique_variants = []
        seen = set()

        for variant in variants:
            key = tuple(sorted(variant.items()))

            if key in seen:
                continue

            seen.add(key)
            unique_variants.append(variant)

        return unique_variants

    def get_time_series(
        self,
        ticker: str,
        interval: str = "1day",
        outputsize: int = 30,
    ) -> dict | None:
        symbol, exchange = self.yahoo_to_twelve_symbol(ticker)

        if not symbol or not self.is_configured():
            return None

        param_variants = [
            {
                **params,
                "interval": interval,
                "outputsize": outputsize,
            }
            for params in self.market_data_param_variants(
                symbol=symbol,
                exchange=exchange,
            )
        ]

        return self._first_successful_request(
            "time_series",
            param_variants,
        )

    def _build_stock_data(
        self,
        ticker: str,
        quote: dict | None,
        price: dict | None,
        eod: dict | None,
    ) -> dict | None:
        payload = quote or price or eod

        if not payload:
            return None

        current_price = (
            self._to_float(payload.get("close"))
            or self._to_float(payload.get("price"))
            or self._to_float(payload.get("close_price"))
        )

        if current_price is None:
            return None

        data_quality_fields = [
            payload.get("open"),
            payload.get("high"),
            payload.get("low"),
            payload.get("previous_close"),
            payload.get("volume"),
            payload.get("percent_change"),
        ]
        available_fields = len(
            [
                value
                for value in data_quality_fields
                if value not in (None, "")
            ]
        )

        return {
            "company_name": payload.get("name") or payload.get("symbol") or ticker,
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
            "currency": payload.get("currency") or "INR",
            "exchange": payload.get("exchange"),
            "previous_close": self._to_float(payload.get("previous_close")),
            "day_open": self._to_float(payload.get("open")),
            "day_high": self._to_float(payload.get("high")),
            "day_low": self._to_float(payload.get("low")),
            "volume": self._to_float(payload.get("volume")),
            "change": self._to_float(payload.get("change")),
            "percent_change": self._to_float(payload.get("percent_change")),
            "is_market_open": payload.get("is_market_open"),
            "provider": "twelve_data",
            "data_quality_score": round(available_fields / len(data_quality_fields), 2),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
