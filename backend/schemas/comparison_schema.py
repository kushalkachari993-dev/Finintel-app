from pydantic import BaseModel
from pydantic import Field
from typing import List
from typing import Dict
from typing import Any
from typing import Optional


class ComparisonResponse(BaseModel):

    comparison_type: str

    companies_compared: List[str]

    summary: str = ""

    comparative_analysis: List[str]

    strengths: Dict[str, Any] = Field(
        default_factory=dict
    )

    risks: Dict[str, Any] = Field(
        default_factory=dict
    )

    winner_summary: str

    balanced_view: str

    confidence_score: float

    confidence_breakdown: Optional[Dict[str, Any]] = None

    sources_used: List[str] = Field(
        default_factory=list
    )

    disclaimer: str
