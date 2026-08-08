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

