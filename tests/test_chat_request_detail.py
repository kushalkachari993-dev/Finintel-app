import pytest
from pydantic import ValidationError

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
