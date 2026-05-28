import pytest
from pydantic import ValidationError
from types import SimpleNamespace

from backend import main
from backend.main import ChatRequest
from backend.main import ConversationContextMessage
from backend.main import contextual_query


def test_chat_request_defaults_to_brief_answer_detail():
    request = ChatRequest(
        query="What is ROE?"
    )

    assert request.answer_detail == "brief"


def test_chat_request_accepts_detailed_answer_detail():
    request = ChatRequest(
        query="What is ROE?",
        answer_detail="detailed"
    )

    assert request.answer_detail == "detailed"


def test_chat_request_rejects_unknown_answer_detail():
    with pytest.raises(
        ValidationError
    ):
        ChatRequest(
            query="What is ROE?",
            answer_detail="long"
        )


def test_contextual_query_expands_short_follow_up():
    expanded = contextual_query(
        "compare it with Infosys",
        [
            ConversationContextMessage(
                role="user",
                content="Analyze TCS fundamentals"
            ),
            ConversationContextMessage(
                role="assistant",
                content="TCS has strong margins."
            )
        ]
    )

    assert "Conversation context" in expanded
    assert "Analyze TCS fundamentals" in expanded
    assert "compare it with Infosys" in expanded


def test_contextual_query_leaves_standalone_query_unchanged():
    query = "Compare HDFC Bank vs ICICI Bank"

    assert contextual_query(
        query,
        [
            ConversationContextMessage(
                role="user",
                content="What is ROE?"
            )
        ]
    ) == query


def test_contextual_query_does_not_treat_it_sector_as_pronoun():
    query = "compare best it stocks in india"

    assert contextual_query(
        query,
        [
            ConversationContextMessage(
                role="user",
                content="Compare HDFC Bank vs ICICI Bank"
            )
        ]
    ) == query


@pytest.mark.anyio
async def test_chat_passes_detailed_mode_to_route_agent(monkeypatch):

    monkeypatch.setattr(
        main.query_intelligence,
        "extract",
        lambda query: {
            "intent": "EDUCATIONAL",
            "companies": []
        }
    )
    monkeypatch.setattr(
        main.router_agent,
        "route",
        lambda query, intelligence=None: {
            "route": "EDUCATIONAL",
            "confidence": 0.9,
            "reasoning": "Mocked route."
        }
    )

    captured = {}

    def explain(query, **kwargs):

        captured.update(
            kwargs
        )

        return {
            "success": True,
            "data": {
                "topic": "ROE",
                "simple_definition": "Return on equity.",
                "detailed_explanation": "Detailed ROE explanation.",
                "why_it_matters": "It shows profitability.",
                "practical_interpretation": "Compare with peers.",
                "limitations": "Can be distorted by leverage.",
                "example": "Profit divided by equity.",
                "confidence_score": 0.9,
                "disclaimer": "Educational only.",
                "sources_used": []
            },
            "error": None
        }

    monkeypatch.setattr(
        main.educational_agent,
        "explain",
        explain
    )

    await main.chat(
        request=ChatRequest(
            query="What is ROE?",
            answer_detail="detailed"
        ),
        http_request=SimpleNamespace(
            state=SimpleNamespace()
        )
    )

    assert captured["answer_detail"] == "detailed"
