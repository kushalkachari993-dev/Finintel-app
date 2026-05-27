from backend.tools.company_context_tool import CompanyContextTool


def test_company_context_tool_filters_and_formats_sources(monkeypatch):

    tool = CompanyContextTool()

    monkeypatch.setattr(
        tool.search_tool,
        "search",
        lambda query, max_results: [
            {
                "title": "Infosys financial overview",
                "content": (
                    "Infosys is an Indian IT services company "
                    "with business performance and margin context."
                ),
                "url": "https://www.moneycontrol.com/example"
            },
            {
                "title": "Untrusted short result",
                "content": "Tiny",
                "url": "https://random.example.com"
            }
        ]
    )

    result = tool.get_company_context(
        company_name="Infosys",
        ticker="INFY.NS"
    )

    assert "Infosys financial overview" in result["context_text"]
    assert result["sources_used"] == [
        "https://www.moneycontrol.com/example"
    ]
    assert len(result["results"]) == 1
