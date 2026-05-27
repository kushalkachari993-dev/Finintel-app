from backend.agents.news_agent import NewsAgent


def test_news_agent_returns_sourced_fallback_when_llm_json_fails(monkeypatch):
    agent = NewsAgent()

    monkeypatch.setattr(
        agent.ticker_resolver,
        "resolve",
        lambda query: {
            "company_name": "Infosys",
            "ticker": "INFY.NS"
        }
    )
    monkeypatch.setattr(
        agent.news_tool,
        "get_company_news",
        lambda company_name: [
            {
                "title": "Infosys shares react to quarterly results",
                "content": "Analysts are watching revenue growth, margins, and guidance.",
                "url": "https://www.moneycontrol.com/example-infosys"
            }
        ]
    )
    monkeypatch.setattr(
        agent.groq,
        "generate_raw",
        lambda **kwargs: "Not JSON."
    )

    response = agent.analyze(
        "Latest news about Infosys",
        intelligence={
            "companies": [
                "Infosys"
            ],
            "intent": "NEWS"
        }
    )

    assert response["success"] is True
    assert response["error"] is None
    assert response["data"]["company_name"] == "Infosys"
    assert response["data"]["ticker"] == "INFY.NS"
    assert response["data"]["key_events"] == [
        "Infosys shares react to quarterly results"
    ]
    assert response["data"]["sources"] == [
        "https://www.moneycontrol.com/example-infosys"
    ]
