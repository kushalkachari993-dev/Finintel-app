import logging
import math
from datetime import datetime
from datetime import timezone

import yfinance as yf

from backend.tools.alpha_vantage_tool import (
    AlphaVantageTool
)

from backend.config.settings import (
    STOCK_DATA_CACHE_SECONDS
)

from backend.tools.financial_normalizer import (
    FinancialNormalizer
)

from backend.tools.financial_validator import (
    FinancialValidator
)

from backend.tools.gemini_grounded_price_tool import (
    GeminiGroundedPriceTool
)

from backend.tools.twelve_data_tool import (
    TwelveDataTool
)

from backend.tools.web_price_search_tool import (
    WebPriceSearchTool
)

from backend.utils.simple_cache import build_cache


logger = logging.getLogger(__name__)


class StockDataTool:

    cache = build_cache(
        ttl_seconds=STOCK_DATA_CACHE_SECONDS,
        namespace="stock_data"
    )

    gemini_grounded_price_tool = GeminiGroundedPriceTool()
    web_price_search_tool = WebPriceSearchTool()
    alpha_vantage_tool = AlphaVantageTool()
    twelve_data_tool = TwelveDataTool()

    PRICE_QUOTE_FIELDS = {
        "current_price",
        "currency",
        "exchange",
        "provider",
        "price_freshness",
        "price_date",
        "source_url",
        "retrieved_at",
        "previous_close",
        "day_open",
        "day_high",
        "day_low",
        "volume",
        "change",
        "percent_change",
        "is_market_open",
    }

    @staticmethod
    def has_valid_price(result) -> bool:
        if not isinstance(result, dict) or result.get("error"):
            return False

        try:
            price = float(result.get("current_price"))
        except (TypeError, ValueError):
            return False

        return math.isfinite(price) and price > 0

    @classmethod
    def merge_price_quote(
        cls,
        base_result: dict,
        quote_result: dict,
    ) -> dict:
        merged = dict(base_result)

        for key, value in quote_result.items():
            if value is None:
                continue
            if key in cls.PRICE_QUOTE_FIELDS or merged.get(key) is None:
                merged[key] = value

        merged["data_quality_score"] = max(
            base_result.get("data_quality_score", 0.0) or 0.0,
            quote_result.get("data_quality_score", 0.0) or 0.0,
        )
        return merged

    def get_fallback_price(
        self,
        *,
        ticker: str,
        company_name: str | None,
    ) -> dict | None:
        providers = (
            (
                "twelve_data",
                lambda: self.twelve_data_tool.get_quote_data(ticker=ticker),
            ),
            (
                "alpha_vantage",
                lambda: self.alpha_vantage_tool.get_quote_data(
                    ticker=ticker,
                    company_name=company_name,
                ),
            ),
            (
                "gemini_grounded_search",
                lambda: self.gemini_grounded_price_tool.search_price(
                    ticker=ticker,
                    company_name=company_name,
                ),
            ),
            (
                "tavily_web_search",
                lambda: self.web_price_search_tool.search_price(
                    ticker=ticker,
                    company_name=company_name,
                ),
            ),
        )

        for provider, fetch_quote in providers:
            try:
                quote = fetch_quote()
            except Exception:
                logger.exception(
                    "stock_price_provider_failed provider=%s ticker=%s",
                    provider,
                    ticker,
                )
                continue

            if self.has_valid_price(quote):
                logger.info(
                    "stock_price_fallback_success provider=%s ticker=%s",
                    provider,
                    ticker,
                )
                return quote

            logger.warning(
                "stock_price_provider_unavailable provider=%s ticker=%s",
                provider,
                ticker,
            )

        return None

    # ---------------------------------------------------
    # GET STOCK DATA
    # ---------------------------------------------------

    def get_stock_data(
        self,
        ticker: str,
        company_name: str | None = None
    ):

        cache_key = ticker.strip().upper()

        cached = self.cache.get(
            cache_key
        )

        if cached is not None:

            logger.info(
                "stock_data_cache_hit ticker=%s",
                ticker
            )

            return cached

        try:

            stock = yf.Ticker(
                ticker
            )

            info = stock.info

            # ---------------------------------------------------
            # BASIC INFO
            # ---------------------------------------------------

            company_name = (
                info.get("longName")
                or company_name
            )

            sector = (
                info.get("sector")
            )

            current_price = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
            )

            market_state = str(
                info.get("marketState")
                or ""
            ).upper()

            is_market_open = (
                market_state == "REGULAR"
                if market_state
                else None
            )

            market_cap = (
                info.get("marketCap")
            )

            # ---------------------------------------------------
            # RAW VALUES
            # ---------------------------------------------------

            pe_ratio = (
                info.get("trailingPE")
            )

            pb_ratio = (
                info.get("priceToBook")
            )

            roe = (
                info.get("returnOnEquity")
            )

            profit_margin = (
                info.get("profitMargins")
            )

            operating_margin = (
                info.get(
                    "operatingMargins"
                )
            )

            revenue_growth = (
                info.get(
                    "revenueGrowth"
                )
            )

            debt_to_equity = (
                info.get(
                    "debtToEquity"
                )
            )

            dividend_yield = (
                info.get(
                    "dividendYield"
                )
            )

            # ---------------------------------------------------
            # NORMALIZATION
            # ---------------------------------------------------

            roe = (
                FinancialNormalizer
                .normalize_percentage(
                    roe
                )
            )

            profit_margin = (
                FinancialNormalizer
                .normalize_percentage(
                    profit_margin
                )
            )

            operating_margin = (
                FinancialNormalizer
                .normalize_percentage(
                    operating_margin
                )
            )

            revenue_growth = (
                FinancialNormalizer
                .normalize_percentage(
                    revenue_growth
                )
            )

            dividend_yield = (
                FinancialNormalizer
                .normalize_percentage(
                    dividend_yield
                )
            )

            pe_ratio = (
                FinancialNormalizer
                .normalize_ratio(
                    pe_ratio
                )
            )

            pb_ratio = (
                FinancialNormalizer
                .normalize_ratio(
                    pb_ratio
                )
            )

            debt_to_equity = (
                FinancialNormalizer
                .normalize_ratio(
                    debt_to_equity
                )
            )

            # ---------------------------------------------------
            # VALIDATION
            # ---------------------------------------------------

            pe_ratio = (
                FinancialValidator
                .validate_pe(
                    pe_ratio
                )
            )

            pb_ratio = (
                FinancialValidator
                .validate_pb(
                    pb_ratio
                )
            )

            roe = (
                FinancialValidator
                .validate_roe(
                    roe
                )
            )

            profit_margin = (
                FinancialValidator
                .validate_margin(
                    profit_margin
                )
            )

            operating_margin = (
                FinancialValidator
                .validate_margin(
                    operating_margin
                )
            )

            revenue_growth = (
                FinancialValidator
                .validate_growth(
                    revenue_growth
                )
            )

            dividend_yield = (
                FinancialValidator
                .validate_dividend_yield(
                    dividend_yield
                )
            )

            debt_to_equity = (
                FinancialValidator
                .validate_debt_to_equity(
                    debt_to_equity
                )
            )

            # ---------------------------------------------------
            # DATA QUALITY SCORE
            # ---------------------------------------------------

            fields = [

                pe_ratio,
                pb_ratio,
                roe,
                profit_margin,
                operating_margin,
                revenue_growth,
                dividend_yield,
                debt_to_equity
            ]

            valid_fields = len(

                [
                    f for f in fields
                    if f is not None
                ]
            )

            data_quality_score = round(
                valid_fields / len(fields),
                2
            )

            # ---------------------------------------------------
            # RETURN CLEAN DATA
            # ---------------------------------------------------

            result = {

                # -----------------------------------
                # BASIC
                # -----------------------------------

                "company_name":
                company_name,

                "sector":
                sector,

                "current_price":
                current_price,

                "currency":
                info.get("currency") or "INR",

                "exchange":
                info.get("exchange"),

                "previous_close":
                info.get("regularMarketPreviousClose"),

                "day_open":
                info.get("regularMarketOpen"),

                "day_high":
                info.get("regularMarketDayHigh"),

                "day_low":
                info.get("regularMarketDayLow"),

                "volume":
                info.get("regularMarketVolume"),

                "change":
                info.get("regularMarketChange"),

                "percent_change":
                info.get("regularMarketChangePercent"),

                "is_market_open":
                is_market_open,

                "provider":
                "yfinance",

                "price_freshness":
                "live_or_delayed",

                "market_cap":
                FinancialNormalizer
                .normalize_market_cap(
                    market_cap
                ),

                # -----------------------------------
                # VALUATION
                # -----------------------------------

                "pe_ratio":
                pe_ratio,

                "pb_ratio":
                pb_ratio,

                # -----------------------------------
                # PROFITABILITY
                # -----------------------------------

                "roe":
                FinancialNormalizer
                .format_percentage(
                    roe
                ),

                "roe_raw":
                roe,

                "profit_margin":
                FinancialNormalizer
                .format_percentage(
                    profit_margin
                ),

                "profit_margin_raw":
                profit_margin,

                "operating_margin":
                FinancialNormalizer
                .format_percentage(
                    operating_margin
                ),

                "operating_margin_raw":
                operating_margin,

                # -----------------------------------
                # GROWTH
                # -----------------------------------

                "revenue_growth":
                FinancialNormalizer
                .format_percentage(
                    revenue_growth
                ),

                "revenue_growth_raw":
                revenue_growth,

                # -----------------------------------
                # DEBT
                # -----------------------------------

                "debt_to_equity":
                debt_to_equity,

                "debt_to_equity_raw":
                debt_to_equity,

                # -----------------------------------
                # DIVIDEND
                # -----------------------------------

                "dividend_yield":
                FinancialNormalizer
                .format_percentage(
                    dividend_yield
                ),

                "dividend_yield_raw":
                dividend_yield,

                # -----------------------------------
                # DATA QUALITY
                # -----------------------------------

                "data_quality_score":
                data_quality_score,

                "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat()
            }

            if not self.has_valid_price(result):
                fallback_result = self.get_fallback_price(
                    ticker=ticker,
                    company_name=company_name,
                )

                if fallback_result:
                    result = self.merge_price_quote(
                        result,
                        fallback_result,
                    )

            if not self.has_valid_price(result):
                return {
                    "error": (
                        "All configured stock price providers are "
                        "currently unavailable."
                    )
                }

            return self.cache.set(
                cache_key,
                result
            )

        except Exception:

            logger.exception(
                "stock_data_fetch_failed ticker=%s",
                ticker
            )

            fallback_result = self.get_fallback_price(
                ticker=ticker,
                company_name=company_name,
            )

            if fallback_result:
                return self.cache.set(
                    cache_key,
                    fallback_result,
                )

            return {
                "error": (
                    "All configured stock price providers are "
                    "currently unavailable."
                )
            }
