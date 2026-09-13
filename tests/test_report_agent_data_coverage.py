from backend.agents.report_agent import ReportAgent


def resolved_banks():
    return [
        {
            "ticker": "HDFCBANK.NS",
            "company_name": "HDFC Bank",
        },
        {
            "ticker": "ICICIBANK.NS",
            "company_name": "ICICI Bank",
        },
    ]


def test_multi_company_report_requires_every_company(monkeypatch):
    agent = ReportAgent()

    monkeypatch.setattr(
        agent,
        "extract_candidates",
        lambda query, intelligence: ["HDFC Bank", "ICICI Bank"],
    )
    monkeypatch.setattr(
        agent,
        "resolve_candidates",
        lambda candidates: resolved_banks(),
    )
    monkeypatch.setattr(
        agent,
        "fetch_report_inputs",
        lambda companies: [
            {
                "success": True,
                "company": companies[0],
                "stock_data": {
                    "current_price": 1500,
                    "market_cap": "12 lakh crore",
                    "pe_ratio": 20,
                },
                "sources": [],
            },
            {
                "success": False,
                "company": companies[1],
                "error": "market_data_unavailable",
                "sources": [],
            },
        ],
    )

    response = agent.generate(
        "Compare HDFC Bank vs ICICI Bank",
        intelligence={"companies": ["HDFC Bank", "ICICI Bank"]},
    )

    assert response["success"] is False
    assert response["data"] is None
    assert "ICICI Bank" in response["error"]
    assert "every requested company" in response["error"]


def test_report_metric_count_ignores_provider_metadata():
    assert ReportAgent.count_research_metrics({
        "current_price": 1500,
        "provider": "twelve_data",
        "retrieved_at": "2026-09-13T12:00:00Z",
    }) == 1
