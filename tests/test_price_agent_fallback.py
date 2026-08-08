from backend.agents.price_agent import PriceAgent


def test_price_agent_returns_successful_fallback_when_live_data_unavailable(monkeypatch):
    agent = PriceAgent()

    monkeypatch.setattr(
        agent.ticker_resolver,
        "resolve",
        lambda query: {
            "ticker": "HDFCBANK.NS",
            "company_name": "HDFC Bank",
            "confidence": 0.97
        }
    )
    monkeypatch.setattr(
        agent.stock_tool,
        "get_stock_data",
        lambda ticker: {
            "error": "market data provider unavailable"
        }
    )

    response = agent.get_price(
        "Current price of HDFC Bank"
    )

    assert response["success"] is True
    assert response["error"] is None
    assert response["data"]["query_type"] == "PRICE_QUERY"
    assert response["data"]["company_name"] == "HDFC Bank"
    assert response["data"]["ticker"] == "HDFCBANK.NS"
    assert response["data"]["current_price"] is None
    assert response["data"]["confidence_score"] == 0.35
    assert "could not be fetched" in response["data"]["message"]
    assert "Could not fetch stock data" not in response["data"]["message"]
