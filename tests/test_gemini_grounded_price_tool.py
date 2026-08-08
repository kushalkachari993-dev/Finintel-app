from backend.tools.gemini_grounded_price_tool import GeminiGroundedPriceTool
from backend.tools.stock_data_tool import StockDataTool


def grounded_payload(
    text: str,
    url: str = "https://www.tickertape.in/stocks/hdfc-bank-HDBK"
):
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": text
                        }
                    ]
                },
                "groundingMetadata": {
                    "groundingChunks": [
                        {
                            "web": {
                                "uri": url,
                                "title": "HDFC Bank Share Price"
                            }
                        }
                    ]
                }
            }
        ]
    }


def test_gemini_grounded_price_maps_json_to_stock_contract():
    tool = GeminiGroundedPriceTool(
        api_key="test-key",
        model="gemini-test"
    )

    tool.request_grounded_price = lambda ticker, company_name: grounded_payload(
        """
        {
          "price": 731.25,
          "currency": "INR",
          "company_name": "HDFC Bank",
          "exchange": "NSE",
          "source_url": "https://www.tickertape.in/stocks/hdfc-bank-HDBK",
          "source_title": "HDFC Bank Share Price",
          "note": "web-observed and may be delayed"
        }
        """
    )

    result = tool.search_price(
        ticker="HDFCBANK.NS",
        company_name="HDFC Bank"
    )

    assert result["provider"] == "gemini_grounded_search"
    assert result["company_name"] == "HDFC Bank"
    assert result["current_price"] == 731.25
    assert result["currency"] == "INR"
    assert result["exchange"] == "NSE"
    assert result["source_url"].startswith("https://www.tickertape.in")


def test_gemini_grounded_price_requires_trusted_source():
    tool = GeminiGroundedPriceTool(
        api_key="test-key",
        model="gemini-test"
    )

    tool.request_grounded_price = lambda ticker, company_name: grounded_payload(
        """
        {
          "price": 731.25,
          "currency": "INR",
          "company_name": "HDFC Bank",
          "exchange": "NSE",
          "source_url": "https://example.com/hdfc",
          "source_title": "Example",
          "note": "web-observed and may be delayed"
        }
        """,
        url="https://example.com/hdfc"
    )

    result = tool.search_price(
        ticker="UNTRUSTEDGEMINI.NS",
        company_name="HDFC Bank"
    )

    assert result["error"] == "Gemini grounded search did not find a trusted price."


def test_stock_data_tool_uses_gemini_before_tavily_when_yfinance_fails(monkeypatch):
    tool = StockDataTool()

    class FailingTicker:

        def __init__(
            self,
            ticker
        ):
            raise RuntimeError("rate limited")

    class FakeGeminiTool:

        def search_price(
            self,
            ticker,
            company_name=None
        ):
            return {
                "company_name": company_name or "Gemini Fallback",
                "current_price": 777.7,
                "provider": "gemini_grounded_search",
                "data_quality_score": 0.25,
            }

    class FailingWebPriceSearchTool:

        def search_price(
            self,
            ticker,
            company_name=None
        ):
            raise AssertionError("Tavily should not run when Gemini works")

    monkeypatch.setattr(
        "backend.tools.stock_data_tool.yf.Ticker",
        FailingTicker
    )
    monkeypatch.setattr(
        tool,
        "gemini_grounded_price_tool",
        FakeGeminiTool()
    )
    monkeypatch.setattr(
        tool,
        "web_price_search_tool",
        FailingWebPriceSearchTool()
    )

    result = tool.get_stock_data(
        "GEMINIFALLBACKTEST.NS",
        company_name="Gemini Fallback"
    )

    assert result["provider"] == "gemini_grounded_search"
    assert result["current_price"] == 777.7


def test_stock_data_tool_uses_tavily_when_gemini_is_unavailable(monkeypatch):
    tool = StockDataTool()

    class FailingTicker:

        def __init__(
            self,
            ticker
        ):
            raise RuntimeError("rate limited")

    class EmptyGeminiTool:

        def search_price(
            self,
            ticker,
            company_name=None
        ):
            return {
                "error": "Gemini unavailable"
            }

    class FakeWebPriceSearchTool:

        def search_price(
            self,
            ticker,
            company_name=None
        ):
            return {
                "company_name": company_name or "Tavily Fallback",
                "current_price": 456.75,
                "provider": "tavily_web_search",
                "data_quality_score": 0.2,
            }

    monkeypatch.setattr(
        "backend.tools.stock_data_tool.yf.Ticker",
        FailingTicker
    )
    monkeypatch.setattr(
        tool,
        "gemini_grounded_price_tool",
        EmptyGeminiTool()
    )
    monkeypatch.setattr(
        tool,
        "web_price_search_tool",
        FakeWebPriceSearchTool()
    )

    result = tool.get_stock_data(
        "TAVILYAFTERGEMINITEST.NS",
        company_name="Tavily Fallback"
    )

    assert result["provider"] == "tavily_web_search"
    assert result["current_price"] == 456.75
