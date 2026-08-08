import logging

from backend.tools.stock_data_tool import (
    StockDataTool
)

from backend.tools.ticker_resolver import (
    TickerResolver
)

from backend.schemas.price_schema import (
    PriceResponse
)


logger = logging.getLogger(__name__)


class PriceAgent:

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        self.stock_tool = StockDataTool()

        self.ticker_resolver = (
            TickerResolver()
        )

    # ---------------------------------------------------
    # UNAVAILABLE PRICE FALLBACK
    # ---------------------------------------------------

    def build_unavailable_price_response(
        self,
        query: str,
        ticker: str,
        company_name: str,
        confidence: float,
        fetch_error: str | None = None
    ):

        fallback_confidence = min(
            confidence,
            0.35
        )

        message = (
            f"{company_name} ({ticker}) was identified, but live stock "
            "price data could not be fetched for this request. This can "
            "happen when the market-data provider is temporarily unavailable "
            "or blocks cloud-hosted requests. Please retry, or use a report "
            "for qualitative context while live price data is unavailable."
        )

        response_payload = {

            "query_type":
            "PRICE_QUERY",

            "company_name":
            company_name,

            "ticker":
            ticker,

            "current_price":
            None,

            "market_cap":
            None,

            "pe_ratio":
            None,

            "sector":
            None,

            "currency":
            "INR",

            "confidence_score":
            fallback_confidence,

            "disclaimer":
            (
                "This information is for educational purposes only "
                "and is not investment advice."
            ),

            "message":
            message
        }

        validated = (
            PriceResponse(
                **response_payload
            )
        )

        logger.warning(
            "price_data_unavailable_fallback query=%r ticker=%s error=%r",
            query,
            ticker,
            fetch_error
        )

        return {
            "success":
            True,

            "data":
            validated.model_dump(),

            "error":
            None
        }

    # ---------------------------------------------------
    # CLEAN QUERY
    # ---------------------------------------------------

    def clean_query(
        self,
        query: str
    ):

        return (

            query.lower()

            .replace("current", "")

            .replace("stock", "")

            .replace("share", "")

            .replace("market", "")

            .replace("price", "")

            .replace("what is", "")

            .replace("how much is", "")

            .replace("trading at", "")

            .replace("latest", "")

            .replace("today", "")

            .strip()
        )

    # ---------------------------------------------------
    # GET PRICE
    # ---------------------------------------------------

    def get_price(
        self,
        query: str,
        answer_detail: str = "brief"
    ):

        # ---------------------------------------------------
        # CLEAN QUERY
        # ---------------------------------------------------

        query_clean = (
            self.clean_query(
                query
            )
        )

        # ---------------------------------------------------
        # RESOLVE COMPANY
        # ---------------------------------------------------

        resolved = (

            self.ticker_resolver
            .resolve(query_clean)
        )

        if not resolved:

            return {

                "success": False,

                "data": None,

                "error":
                "Could not resolve company ticker."
            }

        ticker = resolved.get(
            "ticker"
        )

        company_name = resolved.get(
            "company_name"
        )

        confidence = resolved.get(
            "confidence",
            0.0
        )

        # ---------------------------------------------------
        # FETCH STOCK DATA
        # ---------------------------------------------------

        stock_data = (

            self.stock_tool
            .get_stock_data(
                ticker,
                company_name=company_name
            )
        )

        # ---------------------------------------------------
        # FETCH FAILURE
        # ---------------------------------------------------

        if (
            not stock_data
            or isinstance(
                stock_data,
                dict
            )
            and stock_data.get(
                "error"
            )
        ):

            fetch_error = (
                stock_data.get(
                    "error"
                )
                if isinstance(
                    stock_data,
                    dict
                )
                else None
            )

            return self.build_unavailable_price_response(
                query=query,
                ticker=ticker,
                company_name=company_name,
                confidence=confidence,
                fetch_error=fetch_error
            )

        # ---------------------------------------------------
        # EXTRACT DATA SAFELY
        # ---------------------------------------------------

        current_price = stock_data.get(
            "current_price"
        )

        market_cap = stock_data.get(
            "market_cap"
        )

        pe_ratio = stock_data.get(
            "pe_ratio"
        )

        sector = stock_data.get(
            "sector"
        )

        currency = stock_data.get(
            "currency",
            "INR"
        )

        provider = stock_data.get(
            "provider"
        )

        resolved_company_name = (

            stock_data.get(
                "company_name"
            )
            or company_name
        )

        # ---------------------------------------------------
        # BUILD MESSAGE
        # ---------------------------------------------------

        response_confidence = confidence

        if provider == "tavily_web_search":
            response_confidence = min(
                confidence,
                0.55
            )

        if current_price:

            if provider == "tavily_web_search":

                source_url = stock_data.get(
                    "source_url"
                )

                message = (
                    f"{resolved_company_name} has a latest web-observed "
                    f"price of INR {current_price}. This was extracted from "
                    "a trusted web-search result and may be delayed; verify "
                    "with the exchange or broker before relying on it."
                )

                if source_url:
                    message = (
                        f"{message} Source: {source_url}"
                    )

            elif answer_detail == "detailed":

                message = (
                    f"{resolved_company_name} is currently trading at "
                    f"INR {current_price}. "
                    f"The resolved ticker is {ticker}. "
                    f"Available context shows market cap as "
                    f"{market_cap or 'not available'}, P/E as "
                    f"{pe_ratio if pe_ratio is not None else 'not available'}, "
                    f"and sector as {sector or 'not available'}. "
                    "Use this as a live price check only; verify during market "
                    "hours because prices and valuation metrics can move."
                )

            else:

                message = (

                    f"{resolved_company_name} "
                    f"is currently trading at "
                    f"INR {current_price}."
                )

        else:

            message = (

                f"Price data currently "
                f"unavailable for "
                f"{resolved_company_name}."
            )

        # ---------------------------------------------------
        # RESPONSE PAYLOAD
        # ---------------------------------------------------

        response_payload = {

            "query_type":
            "PRICE_QUERY",

            "company_name":
            resolved_company_name,

            "ticker":
            ticker,

            "current_price":
            current_price,

            "market_cap":
            market_cap,

            "pe_ratio":
            pe_ratio,

            "sector":
            sector,

            "currency":
            currency,

            "confidence_score":
            response_confidence,

            "disclaimer":
            (
                "This information is for educational "
                "purposes only and not investment advice."
            ),

            "message":
            message
        }

        # ---------------------------------------------------
        # SCHEMA VALIDATION
        # ---------------------------------------------------

        try:

            validated = (
                PriceResponse(
                    **response_payload
                )
            )

            return {

                "success": True,

                "data":
                validated.model_dump(),

                "error": None
            }

        except Exception as e:

            return {

                "success": False,

                "data": None,

                "error":
                f"Schema validation failed: {str(e)}"
            }
