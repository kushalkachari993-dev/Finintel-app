from fastapi.testclient import TestClient

from backend import main
from backend.audit import ChatAuditStore
from backend.security.clerk_auth import ClerkAuthenticator


class FakeClerkAuthenticator:
    def authenticate(self, token):
        if token != "clerk-token":
            return None

        return ClerkAuthenticator.user_from_claims(
            {
                "sub": "user_clerk_test",
                "email": "clerk@example.com",
                "name": "Clerk User",
            }
        )


def configure_clerk_routes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        main,
        "clerk_authenticator",
        FakeClerkAuthenticator(),
    )
    monkeypatch.setattr(
        main,
        "chat_audit_store",
        ChatAuditStore(
            database_path=str(tmp_path / "audit.sqlite3")
        ),
    )
    monkeypatch.setattr(
        main.settings,
        "validate_required_settings",
        lambda: None,
    )


def clerk_headers():
    return {
        "Authorization": "Bearer clerk-token",
    }


def test_local_account_routes_are_not_exposed(monkeypatch, tmp_path):
    configure_clerk_routes(monkeypatch, tmp_path)
    routes = [
        ("POST", "/auth/register"),
        ("POST", "/auth/login"),
        ("POST", "/auth/verify-email"),
        ("POST", "/auth/password-reset/request"),
        ("POST", "/auth/password-reset/confirm"),
        ("GET", "/admin/users"),
        ("PATCH", "/admin/users/1"),
    ]

    with TestClient(main.app) as client:
        responses = [
            client.request(method, path, json={})
            for method, path in routes
        ]

    assert all(response.status_code == 404 for response in responses)


def test_auth_me_requires_and_accepts_clerk_token(monkeypatch, tmp_path):
    configure_clerk_routes(monkeypatch, tmp_path)

    with TestClient(main.app) as client:
        unauthorized = client.get("/auth/me")
        authorized = client.get(
            "/auth/me",
            headers=clerk_headers(),
        )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["user"] == {
        "user_id": "user_clerk_test",
        "email": "clerk@example.com",
        "full_name": "Clerk User",
        "role": "user",
        "active": True,
        "email_verified": True,
    }


def test_conversation_routes_use_clerk_principal(monkeypatch, tmp_path):
    configure_clerk_routes(monkeypatch, tmp_path)
    principal_id = "clerk:user_clerk_test"
    first_id = main.chat_audit_store.create_conversation(
        principal_id=principal_id,
        title="HDFC Bank review",
    )
    main.chat_audit_store.create_conversation(
        principal_id=principal_id,
        title="ICICI Bank review",
    )

    with TestClient(main.app) as client:
        searched = client.get(
            "/chat/conversations?limit=1&search=HDFC",
            headers=clerk_headers(),
        )
        renamed = client.patch(
            f"/chat/conversations/{first_id}",
            headers=clerk_headers(),
            json={
                "title": "HDFC Bank investment case",
                "pinned": True,
            },
        )
        organized = client.get(
            "/chat/conversations?limit=1",
            headers=clerk_headers(),
        )
        deleted = client.delete(
            f"/chat/conversations/{first_id}",
            headers=clerk_headers(),
        )
        missing = client.get(
            f"/chat/conversations/{first_id}",
            headers=clerk_headers(),
        )

    assert searched.status_code == 200
    assert searched.json()["conversations"][0]["conversation_id"] == first_id
    assert searched.json()["has_more"] is False
    assert renamed.status_code == 200
    assert organized.json()["has_more"] is True
    assert organized.json()["conversations"][0]["pinned"] is True
    assert deleted.status_code == 200
    assert missing.status_code == 404


def test_metrics_and_observability_endpoints(monkeypatch, tmp_path):
    configure_clerk_routes(monkeypatch, tmp_path)

    with TestClient(main.app) as client:
        health = client.get("/health")
        metrics = client.get("/metrics")
        snapshot = client.get("/observability")
        dashboard = client.get("/observability/dashboard")

    assert health.status_code == 200
    assert metrics.status_code == 200
    assert "finintel_requests_total" in metrics.text
    assert snapshot.status_code == 200
    assert "recent_traces" in snapshot.json()
    assert dashboard.status_code == 200
    assert "FinIntel Observability" in dashboard.text


def test_uptime_monitor_head_requests(monkeypatch, tmp_path):
    configure_clerk_routes(monkeypatch, tmp_path)

    with TestClient(main.app) as client:
        root = client.head("/")
        health = client.head("/health")

    assert root.status_code == 200
    assert health.status_code == 200
    assert root.text == ""
    assert health.text == ""


def test_chat_history_requires_authentication(monkeypatch, tmp_path):
    configure_clerk_routes(monkeypatch, tmp_path)

    with TestClient(main.app) as client:
        response = client.get("/chat/history")

    assert response.status_code == 401


def test_chat_history_returns_clerk_principal_records(monkeypatch, tmp_path):
    configure_clerk_routes(monkeypatch, tmp_path)
    main.chat_audit_store.record_chat(
        request_id="req-history",
        principal_id="clerk:user_clerk_test",
        user_id=None,
        api_client_id=None,
        query="What is ROE?",
        route="EDUCATIONAL",
        routing={"route": "EDUCATIONAL"},
        query_intelligence={"intent": "EDUCATIONAL"},
        response={
            "success": True,
            "data": {"confidence_score": 0.9},
            "error": None,
        },
        latency_ms=10,
    )

    with TestClient(main.app) as client:
        response = client.get(
            "/chat/history",
            headers=clerk_headers(),
        )

    assert response.status_code == 200
    assert response.json()["history"][0]["query"] == "What is ROE?"
