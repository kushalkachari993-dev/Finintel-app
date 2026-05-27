from backend.tools.stock_data_tool import (
    StockDataTool
)

from backend.tools.ticker_resolver import (
    TickerResolver
)

from backend.schemas.price_schema import (
    PriceResponse
)


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
        query: str
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
                ticker
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

            return {

                "success": False,

                "data": None,

                "error":
                "Could not fetch stock data."
            }

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

        resolved_company_name = (

            stock_data.get(
                "company_name"
            )
            or company_name
        )

        # ---------------------------------------------------
        # BUILD MESSAGE
        # ---------------------------------------------------

        if current_price:

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
            confidence,

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
