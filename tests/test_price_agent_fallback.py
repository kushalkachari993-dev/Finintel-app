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
            "price_freshness": "web_observed",
            "retrieved_at": "2026-09-12T08:00:00+00:00",
            "previous_close": 725.0,
            "change": 6.25,
            "percent_change": 0.86,
        }
    )

    response = agent.get_price(
        "Current price of HDFC Bank"
    )

    assert response["success"] is True
    assert response["data"]["current_price"] == 731.25
    assert response["data"]["confidence_score"] == 0.55
    assert response["data"]["provider"] == "tavily_web_search"
    assert response["data"]["source_url"] == "https://www.moneycontrol.com/example"
    assert response["data"]["price_freshness"] == "web_observed"
    assert response["data"]["retrieved_at"] == "2026-09-12T08:00:00+00:00"
    assert response["data"]["previous_close"] == 725.0
    assert response["data"]["change"] == 6.25
    assert response["data"]["percent_change"] == 0.86
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


def test_price_agent_labels_twelve_data_price(monkeypatch):
    agent = PriceAgent()

    monkeypatch.setattr(
        agent.ticker_resolver,
        "resolve",
        lambda query: {
            "ticker": "HDFCBANK.NS",
            "company_name": "HDFC Bank",
            "confidence": 0.97,
        },
    )
    monkeypatch.setattr(
        agent.stock_tool,
        "get_stock_data",
        lambda ticker, company_name=None: {
            "company_name": "HDFC Bank",
            "current_price": 708.25,
            "market_cap": None,
            "pe_ratio": None,
            "sector": None,
            "currency": "INR",
            "provider": "twelve_data",
            "is_market_open": False,
        },
    )

    response = agent.get_price("Current price of HDFC Bank")

    assert response["success"] is True
    assert response["data"]["current_price"] == 708.25
    assert response["data"]["confidence_score"] == 0.9
    assert response["data"]["provider"] == "twelve_data"
    assert response["data"]["source_url"] == "https://twelvedata.com/"
    assert response["data"]["is_market_open"] is False
    assert "Twelve Data" in response["data"]["message"]
    assert "latest available market update" in response["data"]["message"]
