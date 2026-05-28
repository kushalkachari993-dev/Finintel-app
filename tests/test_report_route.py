from types import SimpleNamespace

import pytest

from backend import main
from backend.config import settings
from backend.main import ChatRequest


def report_payload():

    return {
        "report_title": "Analyst report: TCS",
        "query": "Generate a report on TCS",
        "report_type": "ANALYST_REPORT",
        "executive_summary": "TCS is reviewed as a source-backed report.",
        "stock_overview": "TCS is reviewed with source-backed market context.",
        "key_insights": [
            "Margins and growth should be checked together.",
            "Valuation should be compared with peers."
        ],
        "current_performance": "Current performance depends on price and margin trend.",
        "risk_assessment": "Key risk is client spending slowdown.",
        "valuation_outlook": "Valuation is reasonable only if growth holds.",
        "research_view": "Neutral: validate latest filings before acting.",
        "source_quality": {
            "source_count": 1,
            "quality_view": "Lightly sourced report."
        },
        "sector_context": "IT demand and margin trend matter.",
        "companies": [
            {
                "company_name": "TCS",
                "ticker": "TCS.NS",
                "business_snapshot": "Large Indian IT services company.",
                "key_metrics": {
                    "pe_ratio": 25.0,
                    "roe": "45.00%"
                },
                "financial_quality": "Strong profitability.",
                "valuation_view": "Valuation should be compared with growth.",
                "growth_drivers": [
                    "Deal wins"
                ],
                "risks": [
                    "Client spending slowdown"
                ],
                "analyst_takeaway": "Watch margins and growth.",
                "sources": [
                    "https://example.com/tcs"
                ]
            }
        ],
        "comparative_view": "Single-company report.",
        "investment_view": "Research starting point.",
        "watchlist_triggers": [
            "Quarterly results"
        ],
        "key_risks": [
            "Market volatility"
        ],
        "next_checks": [
            "Read latest filings"
        ],
        "sources_used": [
            "https://example.com/tcs"
        ],
        "confidence_score": 0.82,
        "confidence_breakdown": {
            "retrieval_score": 1
        },
        "disclaimer": "Educational only."
    }


@pytest.mark.anyio
async def test_report_endpoint_uses_report_agent_and_complex_model(monkeypatch):

    monkeypatch.setattr(
        settings,
        "GROQ_COMPLEX_MODEL",
        "complex-model"
    )
    monkeypatch.setattr(
        main.query_intelligence,
        "extract",
        lambda query: {
            "intent": "FUNDAMENTAL",
            "companies": [
                "TCS"
            ]
        }
    )

    captured = {}

    def generate(**kwargs):

        captured.update(
            kwargs
        )

        return {
            "success": True,
            "data": report_payload(),
            "error": None
        }

    monkeypatch.setattr(
        main.report_agent,
        "generate",
        generate
    )

    result = await main.report(
        request=ChatRequest(
            query="Generate a report on TCS",
            answer_detail="brief"
        ),
        http_request=SimpleNamespace(
            state=SimpleNamespace()
        )
    )

    assert result["success"] is True
    assert result["route"] == "REPORT"
    assert result["answer_detail"] == "detailed"
    assert result["model"] == "complex-model"
    assert result["response"]["success"] is True
    assert result["response"]["data"]["report_type"] == "ANALYST_REPORT"
    assert result["response"]["data"]["research_view"].startswith("Neutral")
    assert captured["model"] == "complex-model"


@pytest.mark.anyio
async def test_report_endpoint_preserves_conversation_context(monkeypatch):

    monkeypatch.setattr(
        main.query_intelligence,
        "extract",
        lambda query: {
            "intent": "FOLLOW_UP",
            "companies": [
                "Infosys"
            ],
            "analysis_query": query
        }
    )

    captured = {}

    def generate(**kwargs):

        captured.update(
            kwargs
        )

        return {
            "success": True,
            "data": report_payload(),
            "error": None
        }

    monkeypatch.setattr(
        main.report_agent,
        "generate",
        generate
    )

    await main.report(
        request=ChatRequest(
            query="make it detailed",
            conversation_context=[
                {
                    "role": "user",
                    "content": "Tell me about Infosys"
                }
            ]
        ),
        http_request=SimpleNamespace(
            state=SimpleNamespace()
        )
    )

    assert "Conversation context:" in captured["query"]
    assert "Tell me about Infosys" in captured["query"]
