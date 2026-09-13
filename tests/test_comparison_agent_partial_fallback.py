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


def test_comparison_rejects_response_when_live_data_is_unavailable(monkeypatch):
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

    assert response["success"] is False
    assert response["data"] is None
    assert "reliable comparison" in response["error"]
    assert "Please retry later" in response["error"]


def test_comparison_rejects_response_with_one_successful_company(monkeypatch):
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

    assert response["success"] is False
    assert response["data"] is None
    assert "at least two companies" in response["error"]


def test_price_only_data_is_not_enough_for_peer_comparison():
    assert ComparisonAgent.has_comparison_coverage({
        "current_price": 1500,
        "provider": "twelve_data"
    }) is False


def test_two_financial_metrics_are_enough_for_peer_comparison():
    assert ComparisonAgent.has_comparison_coverage({
        "current_price": 1500,
        "pe_ratio": 20,
        "roe": "15%"
    }) is True
