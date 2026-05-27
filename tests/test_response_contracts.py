from backend.schemas.comparison_schema import ComparisonResponse
from backend.schemas.discovery_schema import DiscoveryResponse
from backend.schemas.fundamental_schema import FundamentalResponse
from backend.schemas.news_schema import NewsResponse
from backend.schemas.price_schema import PriceResponse


def test_price_response_exposes_frontend_confidence_contract():

    response = PriceResponse(
        company_name="HDFC Bank",
        ticker="HDFCBANK.NS",
        current_price=100.0,
        market_cap="INR 1.00 Lakh Cr",
        pe_ratio=20.0,
        sector="Financial Services",
        confidence_score=0.9,
        message="HDFC Bank is currently trading at INR 100.0."
    )

    assert response.confidence_score == 0.9
    assert response.query_type == "PRICE_QUERY"
    assert response.disclaimer


def test_agent_schemas_preserve_confidence_breakdown():

    breakdown = {
        "retrieval_score": 1.0
    }

    fundamental = FundamentalResponse(
        company_name="Infosys",
        ticker="INFY.NS",
        analysis_type="GENERAL",
        business_overview="Overview",
        financial_strengths=["Strength"],
        financial_risks=["Risk"],
        valuation_commentary="Valuation",
        overall_view="Balanced",
        confidence_score=0.8,
        confidence_breakdown=breakdown,
        disclaimer="Educational only."
    )

    comparison = ComparisonResponse(
        comparison_type="GENERAL",
        companies_compared=["Infosys", "TCS"],
        summary="Summary",
        comparative_analysis=["Analysis"],
        winner_summary="No definitive winner.",
        balanced_view="Balanced",
        confidence_score=0.8,
        confidence_breakdown=breakdown,
        disclaimer="Educational only."
    )

    discovery = DiscoveryResponse(
        query_type="DISCOVERY",
        summary="Summary",
        key_points=["Point"],
        mentioned_companies=["Infosys"],
        confidence_score=0.8,
        confidence_breakdown=breakdown,
        sources_used=["https://example.com"]
    )

    news = NewsResponse(
        company_name="Infosys",
        ticker="INFY.NS",
        headline_summary="Summary",
        key_events=["Event"],
        market_impact="Impact",
        sentiment="Neutral",
        risk_factors=["Risk"],
        confidence_score=0.8,
        confidence_breakdown=breakdown,
        sources=["https://example.com"]
    )

    assert fundamental.confidence_breakdown == breakdown
    assert comparison.confidence_breakdown == breakdown
    assert discovery.confidence_breakdown == breakdown
    assert news.confidence_breakdown == breakdown
