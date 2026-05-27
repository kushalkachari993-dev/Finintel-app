from backend.audit import ChatAuditStore


def test_chat_audit_store_records_and_lists_history(tmp_path):
    store = ChatAuditStore(
        database_path=str(tmp_path / "audit.sqlite3")
    )

    audit_id = store.record_chat(
        request_id="req-1",
        principal_id="user:1",
        user_id=1,
        api_client_id=None,
        query="What is ROE?",
        route="EDUCATIONAL",
        routing={
            "route": "EDUCATIONAL"
        },
        query_intelligence={
            "intent": "EDUCATIONAL"
        },
        response={
            "success": True,
            "data": {
                "topic": "ROE",
                "confidence_score": 0.9
            },
            "error": None
        },
        answer_detail="detailed",
        model="llama-3.3-70b-versatile",
        latency_ms=123.4
    )

    history = store.list_for_principal(
        "user:1"
    )

    assert audit_id == 1
    assert len(history) == 1
    assert history[0]["query"] == "What is ROE?"
    assert history[0]["route"] == "EDUCATIONAL"
    assert history[0]["confidence_score"] == 0.9
    assert history[0]["response_success"] is True
    assert history[0]["response"]["data"]["topic"] == "ROE"
    assert history[0]["answer_detail"] == "detailed"
    assert history[0]["model"] == "llama-3.3-70b-versatile"


def test_chat_audit_store_records_conversation_messages(tmp_path):
    store = ChatAuditStore(
        database_path=str(tmp_path / "audit.sqlite3")
    )

    conversation_id = store.create_conversation(
        principal_id="user:1",
        title="What is ROE?"
    )

    store.add_message(
        conversation_id=conversation_id,
        principal_id="user:1",
        role="user",
        content="What is ROE?"
    )
    store.add_message(
        conversation_id=conversation_id,
        principal_id="user:1",
        role="assistant",
        content="ROE measures profitability.",
        payload={
            "success": True,
            "query": "What is ROE?"
        }
    )

    conversations = store.list_conversations(
        "user:1"
    )
    messages = store.list_messages(
        principal_id="user:1",
        conversation_id=conversation_id
    )

    assert conversations[0]["conversation_id"] == conversation_id
    assert conversations[0]["title"] == "What is ROE?"
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["payload"]["query"] == "What is ROE?"
