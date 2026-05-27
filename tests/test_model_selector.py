from backend.config import settings
from backend.llm.model_selector import select_groq_model


def test_basic_brief_route_uses_fast_model(monkeypatch):

    monkeypatch.setattr(
        settings,
        "GROQ_FAST_MODEL",
        "fast-model"
    )
    monkeypatch.setattr(
        settings,
        "GROQ_COMPLEX_MODEL",
        "complex-model"
    )

    assert select_groq_model("EDUCATIONAL", "brief") == "fast-model"
    assert select_groq_model("PRICE_QUERY", "brief") == "fast-model"


def test_detailed_route_uses_complex_model(monkeypatch):

    monkeypatch.setattr(
        settings,
        "GROQ_FAST_MODEL",
        "fast-model"
    )
    monkeypatch.setattr(
        settings,
        "GROQ_COMPLEX_MODEL",
        "complex-model"
    )

    assert select_groq_model("EDUCATIONAL", "detailed") == "complex-model"


def test_complex_routes_use_complex_model_even_when_brief(monkeypatch):

    monkeypatch.setattr(
        settings,
        "GROQ_FAST_MODEL",
        "fast-model"
    )
    monkeypatch.setattr(
        settings,
        "GROQ_COMPLEX_MODEL",
        "complex-model"
    )

    assert select_groq_model("COMPARISON", "brief") == "complex-model"
    assert select_groq_model("NEWS", "brief") == "complex-model"
    assert select_groq_model("DISCOVERY", "brief") == "complex-model"
