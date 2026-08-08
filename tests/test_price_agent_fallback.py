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
        lambda ticker, company_name=None: {
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


def test_price_agent_labels_web_observed_price_as_delayed(monkeypatch):
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
        lambda ticker, company_name=None: {
            "company_name": "HDFC Bank",
            "current_price": 731.25,
            "market_cap": None,
            "pe_ratio": None,
            "sector": None,
            "currency": "INR",
            "provider": "tavily_web_search",
            "source_url": "https://www.moneycontrol.com/example",
        }
    )

    response = agent.get_price(
        "Current price of HDFC Bank"
    )

    assert response["success"] is True
    assert response["data"]["current_price"] == 731.25
    assert response["data"]["confidence_score"] == 0.55
    assert "web-observed" in response["data"]["message"]
    assert "may be delayed" in response["data"]["message"]


def test_price_agent_labels_gemini_grounded_price(monkeypatch):
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
        lambda ticker, company_name=None: {
            "company_name": "HDFC Bank",
            "current_price": 731.25,
            "market_cap": None,
            "pe_ratio": None,
            "sector": None,
            "currency": "INR",
            "provider": "gemini_grounded_search",
            "source_url": "https://www.tickertape.in/example",
        }
    )

    response = agent.get_price(
        "Current price of HDFC Bank"
    )

    assert response["success"] is True
    assert response["data"]["confidence_score"] == 0.55
    assert "Google-grounded web search" in response["data"]["message"]
    assert "may be delayed" in response["data"]["message"]


def test_price_agent_labels_alpha_vantage_price_as_end_of_day(monkeypatch):
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
        lambda ticker, company_name=None: {
            "company_name": "HDFC Bank",
            "current_price": 731.25,
            "market_cap": None,
            "pe_ratio": None,
            "sector": None,
            "currency": "INR",
            "provider": "alpha_vantage",
            "price_date": "2026-08-08",
        }
    )

    response = agent.get_price(
        "Current price of HDFC Bank"
    )

    assert response["success"] is True
    assert response["data"]["confidence_score"] == 0.7
    assert "Alpha Vantage" in response["data"]["message"]
    assert "2026-08-08" in response["data"]["message"]
    assert "end-of-day" in response["data"]["message"]
