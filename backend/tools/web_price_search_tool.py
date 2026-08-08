import logging
import re
from datetime import datetime
from datetime import timezone
from urllib.parse import urlparse

from backend.config.settings import (
    STOCK_DATA_CACHE_SECONDS
)
from backend.tools.tavily_search_tool import (
    TavilySearchTool
)
from backend.utils.simple_cache import build_cache


logger = logging.getLogger(__name__)


class WebPriceSearchTool:
    """Last-resort stock price fallback using trusted web-search snippets."""

    cache = build_cache(
        ttl_seconds=STOCK_DATA_CACHE_SECONDS,
        namespace="web_price_search"
    )

    trusted_domains = {
        "bseindia.com",
        "economictimes.indiatimes.com",
        "in.investing.com",
        "investing.com",
        "livemint.com",
        "moneycontrol.com",
        "nseindia.com",
        "screener.in",
        "tickertape.in",
        "tradingview.com",
    }

    price_patterns = [
        re.compile(
            r"(?:share price|stock price|current price|last traded price|"
            r"last price|ltp|trading at|quoting at|quote)"
            r"[^0-9₹]{0,80}(?:₹|rs\.?|inr)?\s*"
            r"([0-9][0-9,]*(?:\.[0-9]+)?)",
            re.IGNORECASE
        ),
        re.compile(
            r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.[0-9]+)?)"
            r"[^a-z0-9]{0,20}"
            r"(?:share price|stock price|current price|last traded price|"
            r"last price|ltp|quoting at|quote)",
            re.IGNORECASE
        ),
    ]

    def __init__(
        self,
        search_tool: TavilySearchTool | None = None
    ):
        self.search_tool = (
            search_tool
            or TavilySearchTool()
        )

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

    def extract_price(
        self,
        text: str
    ) -> float | None:
        for pattern in self.price_patterns:
            match = pattern.search(text)

            if not match:
                continue

            value = match.group(1).replace(",", "")

            try:
                price = float(value)
            except ValueError:
                continue

            if price > 0:
                if price > 250000:
                    continue

                return price

        return None

    def search_price(
        self,
        ticker: str,
        company_name: str | None = None
    ) -> dict | None:
        symbol, exchange = self.ticker_to_search_terms(ticker)

        if not symbol:
            return None

        cache_key = (
            symbol,
            exchange,
            (company_name or "").strip().lower()
        )
        cached = self.cache.get(cache_key)

        if cached is not None:
            logger.info(
                "web_price_search_cache_hit ticker=%s",
                ticker
            )
            return cached

        query_company = (
            company_name
            or symbol
        )
        query = (
            f"{query_company} {symbol} {exchange} share price "
            "current price India moneycontrol tickertape tradingview"
        )

        results = self.search_tool.search(
            query=query,
            max_results=6,
            search_depth="basic"
        )

        for item in results:
            if item.get("error"):
                continue

            url = item.get("url")

            if not self.domain_is_trusted(url):
                continue

            combined_text = " ".join(
                str(value or "")
                for value in (
                    item.get("title"),
                    item.get("content"),
                )
            )
            price = self.extract_price(combined_text)

            if price is None:
                continue

            result = {
                "company_name": company_name or symbol,
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
                "currency": "INR",
                "exchange": exchange,
                "provider": "tavily_web_search",
                "source_url": url,
                "source_title": item.get("title"),
                "data_quality_score": 0.2,
                "retrieved_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            logger.info(
                "web_price_search_success ticker=%s source=%s",
                ticker,
                url
            )

            return self.cache.set(
                cache_key,
                result
            )

        return self.cache.set(
            cache_key,
            {
                "error": "No trusted web-search price result found."
            }
        )
