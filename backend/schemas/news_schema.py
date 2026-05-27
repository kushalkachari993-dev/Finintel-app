from pydantic import BaseModel
from typing import List
from typing import Optional
from typing import Dict
from typing import Any


class NewsResponse(BaseModel):

    company_name: str

    ticker: str

    headline_summary: str

    key_events: List[str]

    market_impact: str

    sentiment: str

    risk_factors: List[str]

    confidence_score: float

    confidence_breakdown: Optional[Dict[str, Any]] = None

    disclaimer: str = (
        "This news analysis is for educational purposes only "
        "and not investment advice."
    )

    sources: List[str]
