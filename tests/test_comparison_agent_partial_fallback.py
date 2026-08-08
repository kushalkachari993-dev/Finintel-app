from backend.agents.comparison_agent import ComparisonAgent


def resolved_bank_companies():
    return [
        {
            "ticker": "HDFCBANK.NS",
            "company_name": "HDFC Bank",
            "exchange": "NSE"
        },
        {
            "ticker": "ICICIBANK.NS",
            "company_name": "ICICI Bank",
            "exchange": "NSE"
        }
    ]


def test_comparison_returns_partial_response_when_live_data_is_unavailable(monkeypatch):
    agent = ComparisonAgent()

    monkeypatch.setattr(
        agent,
        "resolve_companies",
        lambda company_queries: resolved_bank_companies()
    )
    monkeypatch.setattr(
        agent,
        "fetch_company_data",
        lambda resolved_companies: {
            "comparison_data": [],
            "successful_fetches": 0,
            "api_failures": 2
        }
    )

    response = agent.compare(
        "Compare HDFC Bank vs ICICI Bank"
    )

    assert response["success"] is True
    assert response["error"] is None
    assert response["data"]["comparison_type"] == "Peer Comparison"
    assert response["data"]["companies_compared"] == [
        "HDFC Bank",
        "ICICI Bank"
    ]
    assert response["data"]["confidence_score"] == 0.3
    assert response["data"]["confidence_breakdown"]["fallback_used"] is True
    assert "Insufficient valid company data" not in response["data"]["summary"]
    assert "live data was insufficient" in response["data"]["balanced_view"]


def test_comparison_returns_partial_response_with_one_successful_company(monkeypatch):
    agent = ComparisonAgent()

    monkeypatch.setattr(
        agent,
        "resolve_companies",
        lambda company_queries: resolved_bank_companies()
    )
    monkeypatch.setattr(
        agent,
        "fetch_company_data",
        lambda resolved_companies: {
            "comparison_data": [
                {
                    "company_name": "HDFC Bank",
                    "ticker": "HDFCBANK.NS",
                    "stock_data": {
                        "current_price": 1500,
                        "pe_ratio": 20,
                        "roe": "15%"
                    },
                    "interpretation": {}
                }
            ],
            "successful_fetches": 1,
            "api_failures": 1
        }
    )

    response = agent.compare(
        "Compare HDFC Bank vs ICICI Bank"
    )

    assert response["success"] is True
    assert response["data"]["comparison_type"] == "Peer Comparison"
    assert response["data"]["confidence_score"] == 0.45
    assert response["data"]["confidence_breakdown"]["retrieval_score"] == 0.5
    assert any(
        "Current price: 1500" in item
        for item in response["data"]["comparative_analysis"]
    )
    assert any(
        "ICICI Bank" in item
        and "unavailable" in item
        for item in response["data"]["comparative_analysis"]
    )
