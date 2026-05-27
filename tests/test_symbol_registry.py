from backend.tools.symbol_registry import SymbolRegistry


def test_symbol_registry_matches_aliases_with_word_boundaries():
    registry = SymbolRegistry()

    assert registry.extract_company_names(
        "Compare Bajaj Finance vs Titan"
    ) == [
        "Bajaj Finance",
        "Titan Company",
    ]


def test_symbol_registry_does_not_match_alias_inside_words():
    registry = SymbolRegistry()

    assert registry.extract_company_names(
        "What are the benefits of technology investing?"
    ) == []


def test_symbol_registry_resolves_company_to_yahoo_ticker():
    registry = SymbolRegistry()

    company = registry.resolve_company("Infy")

    assert company is not None
    assert company.company_name == "Infosys"
    assert company.yahoo_ticker == "INFY.NS"
