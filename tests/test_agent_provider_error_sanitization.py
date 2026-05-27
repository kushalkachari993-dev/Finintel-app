from backend.agents.comparison_agent import ComparisonAgent
from backend.agents.fundamental_agent import FundamentalAgent
from backend.utils.provider_errors import PROVIDER_QUOTA_ERROR


class RaisingCompletions:
    def create(self, **kwargs):
        raise Exception(
            "Error code: 429 - rate_limit_exceeded tokens per day"
        )


class RaisingChat:
    def __init__(self):
        self.completions = RaisingCompletions()


class RaisingClient:
    def __init__(self):
        self.chat = RaisingChat()


def test_fundamental_agent_hides_raw_provider_quota(monkeypatch):
    agent = FundamentalAgent()
    agent.client = RaisingClient()

    monkeypatch.setattr(
        agent.ticker_resolver,
        "resolve",
        lambda query: {
            "ticker": "TCS.NS",
            "company_name": "TCS"
        }
    )
    monkeypatch.setattr(
        agent.stock_tool,
        "get_stock_data",
        lambda ticker: {
            "current_price": 1000,
            "market_cap": "1 lakh crore"
        }
    )
    monkeypatch.setattr(
        agent.financial_interpreter,
        "generate_interpretation",
        lambda stock_data: {
            "overall": "Stable"
        }
    )
    monkeypatch.setattr(
        agent.company_context_tool,
        "get_company_context",
        lambda company_name, ticker: {
            "context_text": "",
            "sources_used": []
        }
    )

    response = agent.analyze(
        "Fundamental analysis of TCS"
    )

    assert response["success"] is False
    assert response["error"] == PROVIDER_QUOTA_ERROR
    assert "rate_limit_exceeded" not in response["error"]


def test_comparison_agent_hides_raw_provider_quota(monkeypatch):
    agent = ComparisonAgent()
    agent.client = RaisingClient()

    monkeypatch.setattr(
        agent,
        "resolve_companies",
        lambda company_queries: [
            {
                "ticker": "HDFCBANK.NS",
                "company_name": "HDFC Bank"
            },
            {
                "ticker": "ICICIBANK.NS",
                "company_name": "ICICI Bank"
            }
        ]
    )
    monkeypatch.setattr(
        agent,
        "fetch_company_data",
        lambda resolved_companies: {
            "comparison_data": [
                {
                    "company_name": "HDFC Bank",
                    "ticker": "HDFCBANK.NS",
                    "stock_data": {},
                    "interpretation": {}
                },
                {
                    "company_name": "ICICI Bank",
                    "ticker": "ICICIBANK.NS",
                    "stock_data": {},
                    "interpretation": {}
                }
            ],
            "successful_fetches": 2,
            "api_failures": 0
        }
    )
    monkeypatch.setattr(
        agent,
        "fetch_company_contexts",
        lambda comparison_data: [
            (
                company,
                {
                    "context_text": "",
                    "sources_used": []
                }
            )
            for company in comparison_data
        ]
    )

    response = agent.compare(
        "Compare HDFC Bank vs ICICI Bank"
    )

    assert response["success"] is False
    assert response["error"] == PROVIDER_QUOTA_ERROR
    assert "429" not in response["error"]
