import logging
from datetime import datetime
from datetime import timezone

import yfinance as yf

from backend.config.settings import (
    STOCK_DATA_CACHE_SECONDS
)

from backend.tools.financial_normalizer import (
    FinancialNormalizer
)

from backend.tools.financial_validator import (
    FinancialValidator
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

    web_price_search_tool = WebPriceSearchTool()

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
            )

            sector = (
                info.get("sector")
            )

            current_price = (
                info.get("currentPrice")
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

            return self.cache.set(
                cache_key,
                result
            )

        except Exception as e:

            logger.exception(
                "stock_data_fetch_failed ticker=%s",
                ticker
            )

            web_price_result = (
                self.web_price_search_tool
                .search_price(
                    ticker=ticker,
                    company_name=company_name
                )
            )

            if (
                web_price_result
                and "error" not in web_price_result
            ):

                return self.cache.set(
                    cache_key,
                    web_price_result
                )

            return self.cache.set(
                cache_key,
                {

                "error":
                str(e)
                }
            )
