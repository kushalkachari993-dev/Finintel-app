from backend.agents.router_agent import RouterAgent
from backend.intelligence.query_intelligence import QueryIntelligence


def test_educational_ratio_query_is_not_treated_as_comparison():

    intelligence = QueryIntelligence().extract(
        "What is ROE?"
    )

    route = RouterAgent().route(
        "What is ROE?",
        intelligence=intelligence
    )

    assert intelligence["intent"] == "EDUCATIONAL"
    assert intelligence["companies"] == []
    assert route["route"] == "EDUCATIONAL"


def test_price_query_with_what_is_routes_to_price():

    intelligence = QueryIntelligence().extract(
        "What is the current price of HDFC Bank?"
    )

    route = RouterAgent().route(
        "What is the current price of HDFC Bank?",
        intelligence=intelligence
    )

    assert intelligence["intent"] == "PRICE_QUERY"
    assert intelligence["companies"] == [
        "HDFC Bank"
    ]
    assert route["route"] == "PRICE_QUERY"


def test_comparison_requires_comparison_intent():

    intelligence = QueryIntelligence().extract(
        "Tell me about HDFC Bank and ICICI Bank"
    )

    route = RouterAgent().route(
        "Tell me about HDFC Bank and ICICI Bank",
        intelligence=intelligence
    )

    assert intelligence["companies"] == [
        "HDFC Bank",
        "ICICI Bank"
    ]
    assert route["route"] != "COMPARISON"


def test_explicit_comparison_still_routes_to_comparison():

    intelligence = QueryIntelligence().extract(
        "Compare HDFC Bank vs ICICI Bank"
    )

    route = RouterAgent().route(
        "Compare HDFC Bank vs ICICI Bank",
        intelligence=intelligence
    )

    assert route["route"] == "COMPARISON"


def test_symbol_registry_extracts_companies_beyond_demo_seed():

    intelligence = QueryIntelligence().extract(
        "Compare Asian Paints vs Titan"
    )

    assert intelligence["companies"] == [
        "Asian Paints",
        "Titan Company"
    ]


def test_capitalized_market_words_are_not_company_fallbacks():

    intelligence = QueryIntelligence().extract(
        "Buy India stocks with high ROE"
    )

    assert intelligence["companies"] == []
