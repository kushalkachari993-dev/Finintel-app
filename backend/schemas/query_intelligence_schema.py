from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class QueryIntelligenceSchema(
    BaseModel
):

    # ---------------------------------------------------
    # PRIMARY INTENT
    # ---------------------------------------------------

    intent: str

    # ---------------------------------------------------
    # MARKET CONTEXT
    # ---------------------------------------------------

    sector: Optional[str] = None

    geography: Optional[str] = "INDIA"

    scope: str = "COMPANY"

    # ---------------------------------------------------
    # ENTITY EXTRACTION
    # ---------------------------------------------------

    companies: list[str] = Field(
        default_factory=list
    )

    # ---------------------------------------------------
    # INVESTMENT CHARACTERISTICS
    # ---------------------------------------------------

    investment_style: list[str] = Field(
        default_factory=list
    )

    analysis_focus: list[str] = Field(
        default_factory=list
    )

    # ---------------------------------------------------
    # RISK + HORIZON
    # ---------------------------------------------------

    risk_profile: Optional[str] = None

    time_horizon: Optional[str] = None