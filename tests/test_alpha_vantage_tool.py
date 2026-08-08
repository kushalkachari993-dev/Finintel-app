from backend.tools.alpha_vantage_tool import AlphaVantageTool
from backend.tools.stock_data_tool import StockDataTool


def test_alpha_vantage_maps_indian_yahoo_tickers_to_bse_symbols():
    assert AlphaVantageTool.yahoo_to_alpha_symbol("HDFCBANK.NS") == (
        "HDFCBANK.BSE",
        "BSE",
        "INR",
    )
    assert AlphaVantageTool.yahoo_to_alpha_symbol("RELIANCE.BO") == (
        "RELIANCE.BSE",
        "BSE",
        "INR",
    )


def test_alpha_vantage_quote_maps_to_stock_data_contract():
    tool = AlphaVantageTool(
        api_key="test-key",
        base_url="https://example.test/query",
    )

    def fake_request(function, **params):
        assert function == "GLOBAL_QUOTE"
        assert params["symbol"] == "HDFCBANK.BSE"
        return {
            "Global Quote": {
                "01. symbol": "HDFCBANK.BSE",
                "02. open": "729.00",
                "03. high": "735.00",
                "04. low": "725.00",
                "05. price": "731.25",
                "06. volume": "123456",
                "07. latest trading day": "2026-08-08",
                "08. previous close": "728.50",
                "09. change": "2.75",
                "10. change percent": "0.3775%",
            }
        }

    tool._request = fake_request
    result = tool.get_quote_data(
        "HDFCBANK.NS",
        company_name="HDFC Bank",
    )

    assert result["provider"] == "alpha_vantage"
    assert result["company_name"] == "HDFC Bank"
    assert result["current_price"] == 731.25
    assert result["currency"] == "INR"
    assert result["exchange"] == "BSE"
    assert result["price_freshness"] == "end_of_day"
    assert result["price_date"] == "2026-08-08"
    assert result["previous_close"] == 728.5
    assert result["data_quality_score"] == 0.35


def test_alpha_vantage_falls_back_to_latest_daily_close():
    tool = AlphaVantageTool(
        api_key="test-key",
        base_url="https://example.test/query",
    )
    calls = []

    def fake_request(function, **params):
        calls.append(function)

        if function == "GLOBAL_QUOTE":
            return {"Global Quote": {}}

        return {
            "Time Series (Daily)": {
                "2026-08-07": {
                    "1. open": "720.00",
                    "2. high": "734.00",
                    "3. low": "719.00",
                    "4. close": "730.50",
                    "5. volume": "999999",
                },
                "2026-08-06": {
                    "4. close": "722.00",
                },
            }
        }

    tool._request = fake_request
    result = tool.get_quote_data(
        "ALPHADAILYTEST.NS",
        company_name="Alpha Daily Test",
    )

    assert calls == ["GLOBAL_QUOTE", "TIME_SERIES_DAILY"]
    assert result["current_price"] == 730.5
    assert result["price_date"] == "2026-08-07"
    assert result["provider"] == "alpha_vantage"


def test_stock_data_tool_uses_alpha_vantage_before_search_fallbacks(monkeypatch):
    tool = StockDataTool()

    class FailingTicker:

        def __init__(self, ticker):
            raise RuntimeError("rate limited")

    class FakeAlphaVantageTool:

        def get_quote_data(self, ticker, company_name=None):
            return {
                "company_name": company_name or "Alpha Fallback",
                "current_price": 731.25,
                "currency": "INR",
                "provider": "alpha_vantage",
                "price_date": "2026-08-08",
                "data_quality_score": 0.35,
            }

    class UnexpectedSearchFallback:

        def search_price(self, ticker, company_name=None):
            raise AssertionError("Search fallback should not run when Alpha works")

    monkeypatch.setattr(
        "backend.tools.stock_data_tool.yf.Ticker",
        FailingTicker,
    )
    monkeypatch.setattr(
        tool,
        "alpha_vantage_tool",
        FakeAlphaVantageTool(),
    )
    monkeypatch.setattr(
        tool,
        "gemini_grounded_price_tool",
        UnexpectedSearchFallback(),
    )
    monkeypatch.setattr(
        tool,
        "web_price_search_tool",
        UnexpectedSearchFallback(),
    )

    result = tool.get_stock_data(
        "ALPHAFALLBACKTEST.NS",
        company_name="Alpha Fallback",
    )

    assert result["provider"] == "alpha_vantage"
    assert result["current_price"] == 731.25


def test_stock_data_tool_fills_missing_yfinance_price_without_losing_fundamentals(
    monkeypatch,
):
    tool = StockDataTool()

    class PartialTicker:

        def __init__(self, ticker):
            self.info = {
                "longName": "Partial Data Limited",
                "currentPrice": None,
                "trailingPE": 18.5,
                "sector": "Financial Services",
            }

    class FakeAlphaVantageTool:

        def get_quote_data(self, ticker, company_name=None):
            return {
                "company_name": company_name,
                "current_price": 731.25,
                "currency": "INR",
                "exchange": "BSE",
                "provider": "alpha_vantage",
                "price_freshness": "end_of_day",
                "price_date": "2026-08-08",
                "data_quality_score": 0.35,
            }

    monkeypatch.setattr(
        "backend.tools.stock_data_tool.yf.Ticker",
        PartialTicker,
    )
    monkeypatch.setattr(
        tool,
        "alpha_vantage_tool",
        FakeAlphaVantageTool(),
    )

    result = tool.get_stock_data("ALPHAPARTIALTEST.NS")

    assert result["current_price"] == 731.25
    assert result["pe_ratio"] == 18.5
    assert result["sector"] == "Financial Services"
    assert result["provider"] == "alpha_vantage"
