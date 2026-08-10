import pytest
from pydantic import ValidationError
from types import SimpleNamespace

from backend import main
from backend.main import ChatRequest
from backend.main import ConversationContextMessage
from backend.main import conversation_context_for_request
from backend.main import contextual_query
from backend.main import response_context_text


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

    assert expanded == "Compare TCS and Infosys"


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


def test_contextual_query_expands_natural_follow_up():
    expanded = contextual_query(
        "What about its debt trend?",
        [
            ConversationContextMessage(
                role="user",
                content="Analyze Reliance Industries"
            )
        ]
    )

    assert expanded == "What about Reliance Industries's debt trend?"


def test_contextual_query_leaves_short_unrelated_question_unchanged():
    query = "What is inflation?"

    assert contextual_query(
        query,
        [
            ConversationContextMessage(
                role="user",
                content="Analyze TCS fundamentals"
            )
        ]
    ) == query


@pytest.mark.parametrize(
    "query",
    [
        "Why?",
        "And valuation?",
        "More details"
    ]
)
def test_contextual_query_expands_terse_follow_up(query):
    expanded = contextual_query(
        query,
        [
            ConversationContextMessage(
                role="user",
                content="Analyze TCS fundamentals"
            )
        ]
    )

    assert "TCS" in expanded
    assert "Conversation context" not in expanded


def test_contextual_comparison_does_not_leak_answer_fields():
    expanded = contextual_query(
        "compare it with infosys and wipro.",
        [
            ConversationContextMessage(
                role="user",
                content="tell me about tcs."
            ),
            ConversationContextMessage(
                role="assistant",
                content=(
                    '{"sector":"Technology","industry":"Communication '
                    'and Media"}'
                )
            ),
            ConversationContextMessage(
                role="user",
                content="compare it with infosys and wipro."
            ),
            ConversationContextMessage(
                role="error",
                content="Request timed out while waiting for providers."
            ),
            ConversationContextMessage(
                role="user",
                content="compare it with infosys and wipro."
            ),
            ConversationContextMessage(
                role="error",
                content="Streaming response ended before a final answer."
            )
        ]
    )

    assert expanded == (
        "Compare TCS, Infosys, and Wipro"
    )
    assert "Technology" not in expanded
    assert "Communication" not in expanded
    assert main.query_intelligence.extract(
        expanded
    )["companies"] == [
        "TCS",
        "Infosys",
        "Wipro"
    ]
    assert main.comparison_agent.extract_companies(
        expanded
    ) == [
        "TCS",
        "Infosys",
        "Wipro"
    ]


def test_response_context_text_serializes_structured_answer():
    text = response_context_text(
        {
            "success": True,
            "data": {
                "company": "TCS",
                "summary": "Margins remain strong."
            }
        }
    )

    assert '"company":"TCS"' in text
    assert "Margins remain strong." in text


def test_server_conversation_history_overrides_client_context(
    monkeypatch
):
    monkeypatch.setattr(
        main.chat_audit_store,
        "list_messages",
        lambda **_: [
            {
                "role": "user",
                "content": "Analyze TCS",
                "payload": None
            },
            {
                "role": "assistant",
                "content": "Analysis completed.",
                "payload": {
                    "response": {
                        "success": True,
                        "data": {
                            "summary": "TCS has strong margins."
                        }
                    }
                }
            }
        ]
    )

    context = conversation_context_for_request(
        principal_id="clerk:user-1",
        conversation_id="conversation-1",
        client_context=[
            ConversationContextMessage(
                role="user",
                content="Fabricated browser context"
            )
        ]
    )

    assert context[0].content == "Analyze TCS"
    assert "TCS has strong margins." in context[1].content
    assert all(
        "Fabricated" not in message.content
        for message in context
    )


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
