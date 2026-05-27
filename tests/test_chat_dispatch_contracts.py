import pytest
from types import SimpleNamespace

from backend import main
from backend.config import settings
from backend.main import ChatRequest


def success_response(data):

    return {
        "success": True,
        "data": data,
        "error": None
    }


@pytest.mark.anyio
async def test_chat_dispatches_to_each_route_with_mocked_agents(monkeypatch):

    cases = {
        "PRICE_QUERY": (
            "price query",
            "price_agent",
            "get_price",
            success_response({
                "company_name": "HDFC Bank",
                "ticker": "HDFCBANK.NS",
                "current_price": 1500.0,
                "confidence_score": 0.9,
                "disclaimer": "Educational only.",
                "message": "HDFC Bank is currently trading at INR 1500.0."
            })
        ),
        "EDUCATIONAL": (
            "education query",
            "educational_agent",
            "explain",
            success_response({
                "topic": "ROE",
                "simple_definition": "Definition",
                "detailed_explanation": "Explanation",
                "confidence_score": 0.9,
                "disclaimer": "Educational only.",
                "sources_used": [
                    "FinIntel curated finance knowledge base"
                ]
            })
        ),
        "COMPARISON": (
            "comparison query",
            "comparison_agent",
            "compare",
            success_response({
                "comparison_type": "GENERAL",
                "companies_compared": ["A", "B"],
                "comparative_analysis": ["Analysis"],
                "winner_summary": "Balanced",
                "balanced_view": "Balanced",
                "confidence_score": 0.8,
                "sources_used": [
                    "https://example.com"
                ],
                "disclaimer": "Educational only."
            })
        ),
        "NEWS": (
            "news query",
            "news_agent",
            "analyze",
            success_response({
                "company_name": "Infosys",
                "ticker": "INFY.NS",
                "headline_summary": "Summary",
                "key_events": ["Event"],
                "market_impact": "Impact",
                "sentiment": "Neutral",
                "risk_factors": ["Risk"],
                "confidence_score": 0.8,
                "disclaimer": "Educational only.",
                "sources": ["https://example.com"]
            })
        ),
        "DISCOVERY": (
            "discovery query",
            "discovery_agent",
            "discover",
            success_response({
                "query_type": "DISCOVERY",
                "summary": "Summary",
                "key_points": ["Point"],
                "mentioned_companies": ["Infosys"],
                "confidence_score": 0.8,
                "sources_used": ["https://example.com"]
            })
        ),
        "FUNDAMENTAL": (
            "fundamental query",
            "fundamental_agent",
            "analyze",
            success_response({
                "company_name": "TCS",
                "ticker": "TCS.NS",
                "analysis_type": "GENERAL",
                "business_overview": "Overview",
                "financial_strengths": ["Strength"],
                "financial_risks": ["Risk"],
                "valuation_commentary": "Valuation",
                "overall_view": "View",
                "confidence_score": 0.8,
                "sources_used": [
                    "https://example.com"
                ],
                "disclaimer": "Educational only."
            })
        )
    }

    monkeypatch.setattr(
        main.query_intelligence,
        "extract",
        lambda query: {
            "intent": "FUNDAMENTAL",
            "companies": []
        }
    )

    for route, (
        query,
        agent_name,
        method_name,
        response
    ) in cases.items():

        monkeypatch.setattr(
            main.router_agent,
            "route",
            lambda query, intelligence=None, route=route: {
                "route": route,
                "confidence": 0.9,
                "reasoning": "Mocked route."
            }
        )

        agent = getattr(
            main,
            agent_name
        )

        monkeypatch.setattr(
            agent,
            method_name,
            lambda *args, response=response, **kwargs: response
        )

        result = await main.chat(
            request=ChatRequest(
                query=query,
                answer_detail="detailed"
            ),
            http_request=SimpleNamespace(
                state=SimpleNamespace()
            )
        )

        assert result["success"] is True
        assert result["answer_detail"] == "detailed"
        assert result["route"] == route
        assert result["response"]["success"] is True
        assert isinstance(
            result["response"]["data"],
            dict
        )


@pytest.mark.anyio
async def test_chat_selects_fast_model_for_basic_brief_route(monkeypatch):

    monkeypatch.setattr(
        settings,
        "GROQ_FAST_MODEL",
        "fast-model"
    )
    monkeypatch.setattr(
        settings,
        "GROQ_COMPLEX_MODEL",
        "complex-model"
    )
    monkeypatch.setattr(
        main.query_intelligence,
        "extract",
        lambda query: {
            "intent": "EDUCATIONAL",
            "companies": []
        }
    )
    monkeypatch.setattr(
        main.router_agent,
        "route",
        lambda query, intelligence=None: {
            "route": "EDUCATIONAL",
            "confidence": 0.9,
            "reasoning": "Mocked route."
        }
    )

    captured = {}

    def explain(query, **kwargs):

        captured.update(
            kwargs
        )

        return success_response({
            "topic": "ROE",
            "simple_definition": "Definition",
            "detailed_explanation": "Explanation",
            "confidence_score": 0.9,
            "disclaimer": "Educational only."
        })

    monkeypatch.setattr(
        main.educational_agent,
        "explain",
        explain
    )

    result = await main.chat(
        request=ChatRequest(
            query="What is ROE?",
            answer_detail="brief"
        ),
        http_request=SimpleNamespace(
            state=SimpleNamespace()
        )
    )

    assert captured["model"] == "fast-model"
    assert result["model"] == "fast-model"


@pytest.mark.anyio
async def test_chat_selects_complex_model_for_complex_route(monkeypatch):

    monkeypatch.setattr(
        settings,
        "GROQ_FAST_MODEL",
        "fast-model"
    )
    monkeypatch.setattr(
        settings,
        "GROQ_COMPLEX_MODEL",
        "complex-model"
    )
    monkeypatch.setattr(
        main.query_intelligence,
        "extract",
        lambda query: {
            "intent": "NEWS",
            "companies": ["Infosys"]
        }
    )
    monkeypatch.setattr(
        main.router_agent,
        "route",
        lambda query, intelligence=None: {
            "route": "NEWS",
            "confidence": 0.9,
            "reasoning": "Mocked route."
        }
    )

    captured = {}

    def analyze(query, **kwargs):

        captured.update(
            kwargs
        )

        return success_response({
            "company_name": "Infosys",
            "ticker": "INFY.NS",
            "headline_summary": "Summary",
            "key_events": ["Event"],
            "market_impact": "Impact",
            "sentiment": "Neutral",
            "risk_factors": ["Risk"],
            "confidence_score": 0.8,
            "disclaimer": "Educational only.",
            "sources": ["https://example.com"]
        })

    monkeypatch.setattr(
        main.news_agent,
        "analyze",
        analyze
    )

    result = await main.chat(
        request=ChatRequest(
            query="Latest news about Infosys",
            answer_detail="brief"
        ),
        http_request=SimpleNamespace(
            state=SimpleNamespace()
        )
    )

    assert captured["model"] == "complex-model"
    assert result["model"] == "complex-model"
