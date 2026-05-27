from pydantic import BaseModel
from pydantic import Field
from typing import List
from typing import Optional
from typing import Dict
from typing import Any


class FundamentalResponse(BaseModel):

    company_name: str

    ticker: str

    analysis_type: str

    business_overview: str

    financial_strengths: List[str]

    financial_risks: List[str]

    valuation_commentary: str

    overall_view: str

    confidence_score: float

    confidence_breakdown: Optional[Dict[str, Any]] = None

    sources_used: List[str] = Field(
        default_factory=list
    )

    disclaimer: str
