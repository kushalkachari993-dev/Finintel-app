from fastapi.testclient import TestClient

from backend import main
from backend.config import settings
from backend.security import APIKeyAuthenticator


def mock_chat_dependencies(monkeypatch):

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

    monkeypatch.setattr(
        main.educational_agent,
        "explain",
        lambda query, **kwargs: {
            "success": True,
            "data": {
                "topic": "ROE",
                "simple_definition": "Definition",
                "detailed_explanation": "Explanation",
                "why_it_matters": "Useful",
                "practical_interpretation": "Interpret carefully",
                "limitations": "Has limitations",
                "example": "Example",
                "confidence_score": 0.9,
                "disclaimer": "Educational only.",
                "sources_used": [
                    "FinIntel curated finance knowledge base"
                ]
            },
            "error": None
        }
    )


def configure_test_security(monkeypatch):

    monkeypatch.setattr(
        settings,
        "APP_API_KEY",
        "test-key"
    )
    monkeypatch.setattr(
        settings,
        "API_CLIENTS_JSON",
        None
    )
    monkeypatch.setattr(
        main,
        "api_key_authenticator",
        APIKeyAuthenticator(
            clients_json=None,
            legacy_api_key="test-key"
        )
    )
    monkeypatch.setattr(
        settings,
        "validate_required_settings",
        lambda: None
    )
    main.chat_rate_limiter.reset()


def test_chat_requires_api_key(monkeypatch):

    configure_test_security(monkeypatch)

    with TestClient(
        main.app
    ) as client:

        response = client.post(
            "/chat",
            json={
                "query": "What is ROE?"
            }
        )

    assert response.status_code == 401
    assert response.json()["success"] is False


def test_chat_rejects_wrong_api_key(monkeypatch):

    configure_test_security(monkeypatch)

    with TestClient(
        main.app
    ) as client:

        response = client.post(
            "/chat",
            headers={
                "X-API-Key": "wrong-key"
            },
            json={
                "query": "What is ROE?"
            }
        )

    assert response.status_code == 401


def test_chat_accepts_valid_api_key(monkeypatch):

    configure_test_security(monkeypatch)
    mock_chat_dependencies(monkeypatch)

    with TestClient(
        main.app
    ) as client:

        response = client.post(
            "/chat",
            headers={
                "X-API-Key": "test-key"
            },
            json={
                "query": "What is ROE?"
            }
        )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_chat_stream_returns_progress_and_final_events(monkeypatch):

    configure_test_security(monkeypatch)
    mock_chat_dependencies(monkeypatch)

    with TestClient(
        main.app
    ) as client:

        with client.stream(
            "POST",
            "/chat/stream",
            headers={
                "X-API-Key": "test-key"
            },
            json={
                "query": "What is ROE?"
            }
        ) as response:

            body = "".join(
                response.iter_text()
            )

    assert response.status_code == 200
    assert "event: progress" in body
    assert "Understanding your question" in body
    assert "event: final" in body
    assert '"route": "EDUCATIONAL"' in body


def test_chat_rate_limits_valid_api_key(monkeypatch):

    configure_test_security(monkeypatch)
    main.chat_rate_limiter.limit = 1
    mock_chat_dependencies(monkeypatch)

    try:

        with TestClient(
            main.app
        ) as client:

            first = client.post(
                "/chat",
                headers={
                    "X-API-Key": "test-key"
                },
                json={
                    "query": "What is ROE?"
                }
            )

            second = client.post(
                "/chat",
                headers={
                    "X-API-Key": "test-key"
                },
                json={
                    "query": "Explain PE ratio"
                }
            )

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.headers.get("Retry-After")

    finally:

        main.chat_rate_limiter.limit = settings.RATE_LIMIT_PER_MINUTE
        main.chat_rate_limiter.reset()


def test_chat_accepts_hashed_named_api_client(monkeypatch):

    clients_json = (
        "[{\"client_id\":\"frontend\","
        "\"name\":\"Frontend\","
        "\"key_hash\":\""
        + APIKeyAuthenticator.hash_key("client-secret")
        + "\"}]"
    )

    monkeypatch.setattr(
        settings,
        "APP_API_KEY",
        None
    )
    monkeypatch.setattr(
        settings,
        "API_CLIENTS_JSON",
        clients_json
    )
    monkeypatch.setattr(
        main,
        "api_key_authenticator",
        APIKeyAuthenticator(
            clients_json=clients_json,
            legacy_api_key=None
        )
    )
    mock_chat_dependencies(monkeypatch)
    main.chat_rate_limiter.reset()

    with TestClient(
        main.app
    ) as client:

        response = client.post(
            "/chat",
            headers={
                "X-API-Key": "client-secret"
            },
            json={
                "query": "What is ROE?"
            }
        )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_chat_rejects_disabled_api_client(monkeypatch):

    clients_json = (
        "[{\"client_id\":\"disabled\","
        "\"api_key\":\"disabled-secret\","
        "\"active\":false}]"
    )

    monkeypatch.setattr(
        settings,
        "APP_API_KEY",
        None
    )
    monkeypatch.setattr(
        settings,
        "API_CLIENTS_JSON",
        clients_json
    )
    monkeypatch.setattr(
        main,
        "api_key_authenticator",
        APIKeyAuthenticator(
            clients_json=clients_json,
            legacy_api_key=None
        )
    )
    main.chat_rate_limiter.reset()

    with TestClient(
        main.app
    ) as client:

        response = client.post(
            "/chat",
            headers={
                "X-API-Key": "disabled-secret"
            },
            json={
                "query": "What is ROE?"
            }
        )

    assert response.status_code == 401
