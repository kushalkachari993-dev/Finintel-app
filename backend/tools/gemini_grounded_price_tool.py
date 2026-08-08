import json
import logging
import re
from datetime import datetime
from datetime import timezone
from urllib.parse import urlparse

import requests

from backend.config.settings import (
    EXTERNAL_CALL_TIMEOUT_SECONDS,
    GEMINI_API_KEY,
    GEMINI_GROUNDED_MODEL,
    STOCK_DATA_CACHE_SECONDS,
)
from backend.utils.simple_cache import build_cache


logger = logging.getLogger(__name__)


class GeminiGroundedPriceTool:
    """Optional Google Search grounded fallback for stock price snippets."""

    cache = build_cache(
        ttl_seconds=STOCK_DATA_CACHE_SECONDS,
        namespace="gemini_grounded_price"
    )

    trusted_domains = {
        "bseindia.com",
        "economictimes.indiatimes.com",
        "finance.yahoo.com",
        "in.investing.com",
        "investing.com",
        "livemint.com",
        "moneycontrol.com",
        "nseindia.com",
        "screener.in",
        "tickertape.in",
        "tradingview.com",
    }

    def __init__(
        self,
        api_key: str | None = GEMINI_API_KEY,
        model: str = GEMINI_GROUNDED_MODEL,
    ):
        self.api_key = api_key
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def ticker_to_search_terms(
        self,
        ticker: str
    ) -> tuple[str, str]:
        normalized = str(ticker or "").strip().upper()

        if normalized.endswith(".NS"):
            return normalized.removesuffix(".NS"), "NSE"

        if normalized.endswith(".BO"):
            return normalized.removesuffix(".BO"), "BSE"

        return normalized, "NSE"

    def domain_is_trusted(
        self,
        url: str | None
    ) -> bool:
        if not url:
            return False

        host = urlparse(url).hostname or ""
        host = host.lower().removeprefix("www.")

        return any(
            host == domain
            or host.endswith(f".{domain}")
            for domain in self.trusted_domains
        )

    def build_prompt(
        self,
        ticker: str,
        company_name: str | None
    ) -> str:
        symbol, exchange = self.ticker_to_search_terms(ticker)
        display_name = company_name or symbol

        return f"""
Use Google Search to find the latest available Indian stock price for:
Company: {display_name}
Ticker: {symbol}
Exchange: {exchange}

Prefer finance pages from NSE, BSE, Moneycontrol, Tickertape,
TradingView, Investing.com, Yahoo Finance, Economic Times, or LiveMint.

Return ONLY valid JSON, no markdown:
{{
  "price": number or null,
  "currency": "INR",
  "company_name": string,
  "exchange": "{exchange}" or null,
  "source_url": string or null,
  "source_title": string or null,
  "note": "web-observed and may be delayed"
}}

Rules:
- Use the per-share stock price only.
- Do not use market cap, sales, revenue, value traded, or index values.
- If a trusted source does not clearly show a per-share price, return null.
""".strip()

    def request_grounded_price(
        self,
        ticker: str,
        company_name: str | None
    ) -> dict | None:
        if not self.is_configured():
            return None

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": self.build_prompt(
                                ticker=ticker,
                                company_name=company_name
                            )
                        }
                    ]
                }
            ],
            "tools": [
                {
                    "googleSearch": {}
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 500,
            },
        }

        try:
            response = requests.post(
                url,
                params={
                    "key": self.api_key
                },
                json=payload,
                timeout=EXTERNAL_CALL_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception(
                "gemini_grounded_price_request_failed ticker=%s model=%s",
                ticker,
                self.model
            )
            return None

        if not response.ok:
            logger.warning(
                "gemini_grounded_price_http_error ticker=%s model=%s "
                "status_code=%s",
                ticker,
                self.model,
                response.status_code
            )
            return None

        try:
            return response.json()
        except ValueError:
            logger.warning(
                "gemini_grounded_price_invalid_json ticker=%s model=%s",
                ticker,
                self.model
            )
            return None

    def extract_text(
        self,
        payload: dict
    ) -> str:
        candidates = payload.get("candidates") or []

        if not candidates:
            return ""

        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
        )

        return "\n".join(
            str(part.get("text") or "")
            for part in parts
            if isinstance(part, dict)
        ).strip()

    def extract_sources(
        self,
        payload: dict
    ) -> list[dict]:
        candidates = payload.get("candidates") or []

        if not candidates:
            return []

        metadata = (
            candidates[0]
            .get("groundingMetadata")
            or {}
        )
        chunks = metadata.get("groundingChunks") or []
        sources = []

        for chunk in chunks:
            web = chunk.get("web") if isinstance(chunk, dict) else None

            if not web:
                continue

            url = web.get("uri")

            if not self.domain_is_trusted(url):
                continue

            sources.append(
                {
                    "url": url,
                    "title": web.get("title"),
                }
            )

        return sources

    def parse_json_text(
        self,
        text: str
    ) -> dict | None:
        cleaned = re.sub(
            r"```(?:json)?|```",
            "",
            text or ""
        ).strip()

        match = re.search(
            r"\{.*\}",
            cleaned,
            flags=re.DOTALL
        )

        if match:
            cleaned = match.group(0)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return None

        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def to_float(
        value
    ) -> float | None:
        if value in (None, ""):
            return None

        try:
            price = float(
                str(value).replace(",", "")
            )
        except (TypeError, ValueError):
            return None

        if price <= 0 or price > 250000:
            return None

        return price

    def search_price(
        self,
        ticker: str,
        company_name: str | None = None
    ) -> dict | None:
        symbol, exchange = self.ticker_to_search_terms(ticker)

        if not symbol or not self.is_configured():
            return None

        cache_key = (
            symbol,
            exchange,
            (company_name or "").strip().lower(),
            self.model,
        )
        cached = self.cache.get(cache_key)

        if cached is not None:
            logger.info(
                "gemini_grounded_price_cache_hit ticker=%s",
                ticker
            )
            return cached

        payload = self.request_grounded_price(
            ticker=ticker,
            company_name=company_name
        )

        if not payload:
            return self.cache.set(
                cache_key,
                {
                    "error": "Gemini grounded search did not return a response."
                }
            )

        parsed = self.parse_json_text(
            self.extract_text(payload)
        )
        sources = self.extract_sources(payload)

        if not parsed:
            return self.cache.set(
                cache_key,
                {
                    "error": "Gemini grounded search did not return parseable JSON."
                }
            )

        price = self.to_float(
            parsed.get("price")
        )
        source_url = parsed.get("source_url")
        source_title = parsed.get("source_title")

        if not self.domain_is_trusted(source_url) and sources:
            source_url = sources[0].get("url")
            source_title = sources[0].get("title")

        if price is None or not self.domain_is_trusted(source_url):
            return self.cache.set(
                cache_key,
                {
                    "error": "Gemini grounded search did not find a trusted price."
                }
            )

        result = {
            "company_name": parsed.get("company_name") or company_name or symbol,
            "sector": None,
            "current_price": price,
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
            "currency": parsed.get("currency") or "INR",
            "exchange": parsed.get("exchange") or exchange,
            "provider": "gemini_grounded_search",
            "source_url": source_url,
            "source_title": source_title,
            "data_quality_score": 0.25,
            "retrieved_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        logger.info(
            "gemini_grounded_price_success ticker=%s source=%s",
            ticker,
            source_url
        )

        return self.cache.set(
            cache_key,
            result
        )
