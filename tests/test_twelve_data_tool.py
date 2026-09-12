from backend.tools.stock_data_tool import StockDataTool
from backend.tools.twelve_data_tool import TwelveDataTool


def test_twelve_data_quote_maps_to_stock_data_contract():
    tool = TwelveDataTool(
        api_key="test-key",
        base_url="https://example.test"
    )

    def fake_request(endpoint, params):
        assert endpoint == "quote"
        assert params["symbol"] == "HDFCBANK:NSE"
        return {
            "symbol": "HDFCBANK",
            "name": "HDFC Bank Limited",
            "exchange": "NSE",
            "currency": "INR",
            "close": "731.00",
            "open": "720.00",
            "high": "735.00",
            "low": "718.00",
            "previous_close": "722.00",
            "volume": "1000000",
            "change": "9.00",
            "percent_change": "1.25",
            "is_market_open": False,
        }

    tool._request = fake_request

    result = tool.get_quote_data("HDFCBANK.NS")

    assert result["provider"] == "twelve_data"
    assert result["company_name"] == "HDFC Bank Limited"
    assert result["current_price"] == 731.0
    assert result["currency"] == "INR"
    assert result["exchange"] == "NSE"
    assert result["previous_close"] == 722.0
    assert result["data_quality_score"] == 1.0


def test_twelve_data_falls_back_to_eod_when_quote_and_price_are_unavailable():
    tool = TwelveDataTool(
        api_key="test-key",
        base_url="https://example.test"
    )
    calls = []

    def fake_request(endpoint, params):
        calls.append(endpoint)

        if endpoint == "eod":
            return {
                "symbol": "ICICIBANK",
                "exchange": "NSE",
                "currency": "INR",
                "close": "728.50",
            }

        return None

    tool._request = fake_request

    result = tool.get_quote_data("ICICIBANK.NS")

    assert calls[:5] == ["quote"] * 5
    assert calls[5:10] == ["price"] * 5
    assert calls[-1] == "eod"
    assert result["current_price"] == 728.5
    assert result["provider"] == "twelve_data"


def test_twelve_data_market_data_variants_prefer_colon_exchange_symbol():
    tool = TwelveDataTool(
        api_key="test-key",
        base_url="https://example.test"
    )

    assert tool.market_data_param_variants(
        symbol="HDFCBANK",
        exchange="NSE"
    ) == [
        {
            "symbol": "HDFCBANK:NSE",
        },
        {
            "symbol": "HDFCBANK",
            "mic_code": "XNSE",
        },
        {
            "symbol": "HDFCBANK",
            "exchange": "NSE",
        },
        {
            "symbol": "HDFCBANK",
            "country": "India",
        },
        {
            "symbol": "HDFCBANK",
        },
    ]


def test_twelve_data_symbol_resolution_prefers_nse():
    tool = TwelveDataTool(
        api_key="test-key",
        base_url="https://example.test"
    )

    result = tool.select_best_symbol(
        [
            {
                "symbol": "HDFCBANK",
                "instrument_name": "HDFC Bank Limited",
                "exchange": "BSE",
                "instrument_type": "Common Stock",
            },
            {
                "symbol": "HDFCBANK",
                "instrument_name": "HDFC Bank Limited",
                "exchange": "NSE",
                "instrument_type": "Common Stock",
            },
        ]
    )

    assert result == {
        "ticker": "HDFCBANK.NS",
        "company_name": "HDFC Bank Limited",
        "exchange": "NSE",
        "confidence": 0.82,
        "provider": "twelve_data",
    }


def test_stock_data_tool_uses_twelve_data_when_yfinance_fails(monkeypatch):
    tool = StockDataTool()

    class FailingTicker:
        def __init__(self, ticker):
            raise RuntimeError("Yahoo blocked the request")

    class FakeTwelveDataTool:
        def get_quote_data(self, ticker):
            return {
                "company_name": "HDFC Bank Limited",
                "current_price": 708.25,
                "currency": "INR",
                "exchange": "NSE",
                "provider": "twelve_data",
                "data_quality_score": 0.8,
            }

    class UnexpectedFallback:
        def get_quote_data(self, *args, **kwargs):
            raise AssertionError("later fallback should not run")

        def search_price(self, *args, **kwargs):
            raise AssertionError("later fallback should not run")

    monkeypatch.setattr(
        "backend.tools.stock_data_tool.yf.Ticker",
        FailingTicker,
    )
    monkeypatch.setattr(tool, "twelve_data_tool", FakeTwelveDataTool())
    monkeypatch.setattr(tool, "alpha_vantage_tool", UnexpectedFallback())
    monkeypatch.setattr(
        tool,
        "gemini_grounded_price_tool",
        UnexpectedFallback(),
    )
    monkeypatch.setattr(tool, "web_price_search_tool", UnexpectedFallback())

    result = tool.get_stock_data(
        "TWELVEFALLBACKTEST.NS",
        company_name="HDFC Bank",
    )

    assert result["provider"] == "twelve_data"
    assert result["current_price"] == 708.25


def test_twelve_data_quote_fills_partial_yfinance_data(monkeypatch):
    tool = StockDataTool()

    class PartialTicker:
        def __init__(self, ticker):
            self.info = {
                "longName": "HDFC Bank Limited",
                "currentPrice": None,
                "regularMarketPrice": None,
                "marketCap": 10_920_000_000_000,
                "trailingPE": 15.18,
                "sector": "Financial Services",
            }

    class FakeTwelveDataTool:
        def get_quote_data(self, ticker):
            return {
                "company_name": "HDFCBANK",
                "current_price": 708.25,
                "currency": "INR",
                "exchange": "NSE",
                "provider": "twelve_data",
                "previous_close": 693.8,
                "data_quality_score": 0.8,
            }

    monkeypatch.setattr(
        "backend.tools.stock_data_tool.yf.Ticker",
        PartialTicker,
    )
    monkeypatch.setattr(tool, "twelve_data_tool", FakeTwelveDataTool())

    result = tool.get_stock_data("TWELVEPARTIALTEST.NS")

    assert result["company_name"] == "HDFC Bank Limited"
    assert result["current_price"] == 708.25
    assert result["provider"] == "twelve_data"
    assert result["previous_close"] == 693.8
    assert result["market_cap"] == "INR 10.92 Lakh Cr"
    assert result["pe_ratio"] == 15.18
    assert result["sector"] == "Financial Services"


def test_yfinance_regular_market_price_avoids_fallbacks(monkeypatch):
    tool = StockDataTool()

    class PartialTicker:
        def __init__(self, ticker):
            self.info = {
                "longName": "Regular Market Price Limited",
                "currentPrice": None,
                "regularMarketPrice": 501.5,
                "regularMarketPreviousClose": 498.0,
                "regularMarketOpen": 499.0,
                "regularMarketDayHigh": 505.0,
                "regularMarketDayLow": 497.5,
                "regularMarketVolume": 125000,
                "regularMarketChange": 3.5,
                "regularMarketChangePercent": 0.7,
                "marketState": "REGULAR",
                "exchange": "NSE",
            }

    class UnexpectedTwelveDataTool:
        def get_quote_data(self, ticker):
            raise AssertionError("fallback should not run")

    monkeypatch.setattr(
        "backend.tools.stock_data_tool.yf.Ticker",
        PartialTicker,
    )
    monkeypatch.setattr(
        tool,
        "twelve_data_tool",
        UnexpectedTwelveDataTool(),
    )

    result = tool.get_stock_data("REGULARMARKETPRICETEST.NS")

    assert result["current_price"] == 501.5
    assert result["provider"] == "yfinance"
    assert result["previous_close"] == 498.0
    assert result["day_high"] == 505.0
    assert result["percent_change"] == 0.7
    assert result["is_market_open"] is True
    assert result["exchange"] == "NSE"


def test_price_fallback_chain_skips_errors_and_invalid_prices(monkeypatch):
    tool = StockDataTool()
    calls = []

    class FailingTicker:
        def __init__(self, ticker):
            raise RuntimeError("Yahoo unavailable")

    class InvalidTwelveDataTool:
        def get_quote_data(self, ticker):
            calls.append("twelve_data")
            return {"current_price": None, "provider": "twelve_data"}

    class FailingAlphaVantageTool:
        def get_quote_data(self, ticker, company_name=None):
            calls.append("alpha_vantage")
            raise RuntimeError("Alpha unavailable")

    class InvalidGeminiTool:
        def search_price(self, ticker, company_name=None):
            calls.append("gemini")
            return {"current_price": 0, "provider": "gemini_grounded_search"}

    class WorkingWebPriceTool:
        def search_price(self, ticker, company_name=None):
            calls.append("tavily")
            return {
                "company_name": company_name,
                "current_price": 456.75,
                "provider": "tavily_web_search",
            }

    monkeypatch.setattr(
        "backend.tools.stock_data_tool.yf.Ticker",
        FailingTicker,
    )
    monkeypatch.setattr(tool, "twelve_data_tool", InvalidTwelveDataTool())
    monkeypatch.setattr(
        tool,
        "alpha_vantage_tool",
        FailingAlphaVantageTool(),
    )
    monkeypatch.setattr(tool, "gemini_grounded_price_tool", InvalidGeminiTool())
    monkeypatch.setattr(tool, "web_price_search_tool", WorkingWebPriceTool())

    result = tool.get_stock_data(
        "ORDEREDFALLBACKTEST.NS",
        company_name="Fallback Limited",
    )

    assert calls == ["twelve_data", "alpha_vantage", "gemini", "tavily"]
    assert result["current_price"] == 456.75
    assert result["provider"] == "tavily_web_search"

