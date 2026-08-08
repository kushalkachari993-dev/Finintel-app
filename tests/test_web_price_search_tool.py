from backend.tools.stock_data_tool import StockDataTool
from backend.tools.web_price_search_tool import WebPriceSearchTool


class FakeSearchTool:

    def __init__(
        self,
        results
    ):
        self.results = results

    def search(
        self,
        query,
        max_results=5,
        search_depth="advanced"
    ):
        return self.results


def test_web_price_search_extracts_price_from_trusted_domain():
    tool = WebPriceSearchTool(
        search_tool=FakeSearchTool(
            [
                {
                    "title": "HDFC Bank Share Price",
                    "content": "HDFC Bank share price is ₹731.25 on NSE today.",
                    "url": "https://www.moneycontrol.com/india/stockpricequote/banks/hdfcbank/HDF01",
                }
            ]
        )
    )

    result = tool.search_price(
        ticker="HDFCBANK.NS",
        company_name="HDFC Bank"
    )

    assert result["provider"] == "tavily_web_search"
    assert result["company_name"] == "HDFC Bank"
    assert result["current_price"] == 731.25
    assert result["currency"] == "INR"
    assert result["source_url"].startswith("https://www.moneycontrol.com")


def test_web_price_search_does_not_extract_unlabelled_rupee_values():
    tool = WebPriceSearchTool(
        search_tool=FakeSearchTool(
            []
        )
    )

    assert tool.extract_price(
        "Market Cap ₹1,134,439 Cr. Sales ₹80,000 Cr."
    ) is None


def test_web_price_search_extracts_current_price_not_market_cap():
    tool = WebPriceSearchTool(
        search_tool=FakeSearchTool(
            []
        )
    )

    assert tool.extract_price(
        "Market Cap ₹1,134,439 Cr. Current Price ₹731.25"
    ) == 731.25


def test_web_price_search_extracts_quoting_at_phrase():
    tool = WebPriceSearchTool(
        search_tool=FakeSearchTool(
            []
        )
    )

    assert tool.extract_price(
        "The stock is quoting at Rs 795.9, up 1.12% on the NSE."
    ) == 795.9


def test_web_price_search_ignores_untrusted_domain():
    tool = WebPriceSearchTool(
        search_tool=FakeSearchTool(
            [
                {
                    "title": "Random HDFC Bank Price",
                    "content": "Price ₹1.00",
                    "url": "https://example.com/hdfc-bank",
                }
            ]
        )
    )

    result = tool.search_price(
        ticker="UNTRUSTEDTEST.NS",
        company_name="HDFC Bank"
    )

    assert result["error"] == "No trusted web-search price result found."


def test_stock_data_tool_uses_yfinance_before_web_search(monkeypatch):
    tool = StockDataTool()

    class FakeTicker:

        def __init__(
            self,
            ticker
        ):
            self.info = {
                "longName": "YFinance Test Limited",
                "currentPrice": 123.45,
                "marketCap": 100000000,
                "sector": "Financial Services",
            }

    class FailingWebPriceSearchTool:

        def search_price(
            self,
            ticker,
            company_name=None
        ):
            raise AssertionError("web search should not run when yfinance works")

    monkeypatch.setattr(
        "backend.tools.stock_data_tool.yf.Ticker",
        FakeTicker
    )
    monkeypatch.setattr(
        tool,
        "web_price_search_tool",
        FailingWebPriceSearchTool()
    )

    result = tool.get_stock_data(
        "YFPRIMARYTEST.NS"
    )

    assert result["company_name"] == "YFinance Test Limited"
    assert result["current_price"] == 123.45


def test_stock_data_tool_uses_web_search_when_yfinance_fails(monkeypatch):
    tool = StockDataTool()

    class FailingTicker:

        def __init__(
            self,
            ticker
        ):
            raise RuntimeError("rate limited")

    class FakeWebPriceSearchTool:

        def search_price(
            self,
            ticker,
            company_name=None
        ):
            return {
                "company_name": company_name or "Fallback Test",
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
        "web_price_search_tool",
        FakeWebPriceSearchTool()
    )

    result = tool.get_stock_data(
        "WEBFALLBACKTEST.NS",
        company_name="Fallback Test"
    )

    assert result["provider"] == "tavily_web_search"
    assert result["company_name"] == "Fallback Test"
    assert result["current_price"] == 456.75
