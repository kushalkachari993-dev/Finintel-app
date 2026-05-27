from pydantic import BaseModel
from typing import Optional


class PriceResponse(BaseModel):

    query_type: str = "PRICE_QUERY"

    company_name: str

    ticker: str

    current_price: Optional[float]

    market_cap: Optional[str]

    pe_ratio: Optional[float]

    sector: Optional[str]

    currency: Optional[str] = "INR"

    confidence_score: float = 0.0

    disclaimer: str = (
        "This information is for educational purposes only "
        "and not investment advice."
    )

    message: str
