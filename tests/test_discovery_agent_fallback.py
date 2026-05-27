from backend.agents.discovery_agent import DiscoveryAgent


def test_discovery_agent_returns_sourced_fallback_when_llm_json_fails(monkeypatch):
    agent = DiscoveryAgent()

    monkeypatch.setattr(
        agent.search_tool,
        "search",
        lambda query, max_results=7: [
            {
                "title": "Undervalued stocks - Screener",
                "content": "S.No. | Name | CMP Rs. | P/E | Mar Cap Rs.Cr. | Qtr Sales Var % | 1. | SPARC | 209.77 | 4.35 | 6807.49",
                "url": "https://www.moneycontrol.com/example"
            }
        ]
    )
    monkeypatch.setattr(
        agent.groq,
        "generate_raw",
        lambda **kwargs: "This is not JSON."
    )

    response = agent.discover(
        "Top undervalued IT stocks in India",
        intelligence={
            "sector": "IT",
            "investment_style": [
                "VALUE"
            ],
            "analysis_focus": [
                "VALUATION"
            ]
        }
    )

    assert response["success"] is True
    assert response["error"] is None
    assert response["data"]["query_type"] == "DISCOVERY"
    assert response["data"]["key_points"]
    assert "model response could not be parsed" not in response["data"]["summary"]
    assert all(
        "CMP Rs" not in point
        for point in response["data"]["key_points"]
    )
    assert response["data"]["sources_used"] == [
        "https://www.moneycontrol.com/example"
    ]
