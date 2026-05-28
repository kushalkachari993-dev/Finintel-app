from typing import Any

from pydantic import BaseModel
from pydantic import Field


class ReportCompanySection(BaseModel):

    company_name: str
    ticker: str
    business_snapshot: str = ""
    key_metrics: dict[str, Any] = Field(
        default_factory=dict
    )
    financial_quality: str = ""
    valuation_view: str = ""
    growth_drivers: list[str] = Field(
        default_factory=list
    )
    risks: list[str] = Field(
        default_factory=list
    )
    analyst_takeaway: str = ""
    sources: list[str] = Field(
        default_factory=list
    )


class ReportResponse(BaseModel):

    report_title: str
    query: str
    report_type: str = "ANALYST_REPORT"
    executive_summary: str
    stock_overview: str = ""
    key_insights: list[str] = Field(
        default_factory=list
    )
    current_performance: str = ""
    risk_assessment: str = ""
    valuation_outlook: str = ""
    research_view: str = ""
    source_quality: dict[str, Any] = Field(
        default_factory=dict
    )
    sector_context: str = ""
    companies: list[ReportCompanySection] = Field(
        default_factory=list
    )
    comparative_view: str = ""
    investment_view: str
    watchlist_triggers: list[str] = Field(
        default_factory=list
    )
    key_risks: list[str] = Field(
        default_factory=list
    )
    next_checks: list[str] = Field(
        default_factory=list
    )
    sources_used: list[str] = Field(
        default_factory=list
    )
    confidence_score: float
    confidence_breakdown: dict[str, Any] | None = None
    disclaimer: str
