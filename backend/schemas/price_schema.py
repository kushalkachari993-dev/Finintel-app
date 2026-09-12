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

    exchange: Optional[str] = None

    provider: Optional[str] = None

    price_freshness: Optional[str] = None

    price_date: Optional[str] = None

    source_url: Optional[str] = None

    retrieved_at: Optional[str] = None

    previous_close: Optional[float] = None

    day_open: Optional[float] = None

    day_high: Optional[float] = None

    day_low: Optional[float] = None

    volume: Optional[float] = None

    change: Optional[float] = None

    percent_change: Optional[float] = None

    is_market_open: Optional[bool] = None

    confidence_score: float = 0.0

    disclaimer: str = (
        "This information is for educational purposes only "
        "and not investment advice."
    )

    message: str
