from fastapi.testclient import TestClient

from backend import main
from backend.security.user_auth import TokenService
from backend.security.user_auth import UserStore
from backend.audit import ChatAuditStore


def configure_auth_routes(monkeypatch, tmp_path):
    store = UserStore(
        database_path=str(tmp_path / "users.sqlite3")
    )
    tokens = TokenService(
        secret="test-secret",
        expire_minutes=5
    )

    monkeypatch.setattr(
        main,
        "user_store",
        store
    )
    monkeypatch.setattr(
        main,
        "token_service",
        tokens
    )
    monkeypatch.setattr(
        main,
        "chat_audit_store",
        ChatAuditStore(
            database_path=str(tmp_path / "audit.sqlite3")
        )
    )
    monkeypatch.setattr(
        main.settings,
        "AUTH_ALLOW_REGISTRATION",
        True
    )
    monkeypatch.setattr(
        main.settings,
        "validate_required_settings",
        lambda: None
    )


def test_register_login_and_me(monkeypatch, tmp_path):
    configure_auth_routes(
        monkeypatch,
        tmp_path
    )

    with TestClient(
        main.app
    ) as client:
        registered = client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "password": "strong-password",
                "full_name": "Test User"
            }
        )
        logged_in = client.post(
            "/auth/login",
            json={
                "email": "user@example.com",
                "password": "strong-password"
            }
        )
        token = logged_in.json()["access_token"]
        profile = client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {token}"
            }
        )

    assert registered.status_code == 200
    assert registered.json()["email_verification_required"] is True
    assert registered.json()["dev_email_verification_token"]
    assert logged_in.status_code == 200
    assert profile.status_code == 200
    assert profile.json()["user"]["email"] == "user@example.com"
    assert profile.json()["user"]["email_verified"] is False


def test_verify_email_route(monkeypatch, tmp_path):
    configure_auth_routes(
        monkeypatch,
        tmp_path
    )

    with TestClient(
        main.app
    ) as client:
        registered = client.post(
            "/auth/register",
            json={
                "email": "verify-route@example.com",
                "password": "strong-password",
                "full_name": "Verify Route"
            }
        )
        token = registered.json()["dev_email_verification_token"]
        verified = client.post(
            "/auth/verify-email",
            json={
                "token": token
            }
        )
        reused = client.post(
            "/auth/verify-email",
            json={
                "token": token
            }
        )

    assert verified.status_code == 200
    assert verified.json()["user"]["email_verified"] is True
    assert reused.status_code == 400


def test_password_reset_routes(monkeypatch, tmp_path):
    configure_auth_routes(
        monkeypatch,
        tmp_path
    )

    with TestClient(
        main.app
    ) as client:
        client.post(
            "/auth/register",
            json={
                "email": "reset-route@example.com",
                "password": "old-password",
                "full_name": "Reset Route"
            }
        )
        reset_request = client.post(
            "/auth/password-reset/request",
            json={
                "email": "reset-route@example.com"
            }
        )
        reset_token = reset_request.json()["dev_password_reset_token"]
        reset_confirm = client.post(
            "/auth/password-reset/confirm",
            json={
                "token": reset_token,
                "new_password": "new-password"
            }
        )
        logged_in = client.post(
            "/auth/login",
            json={
                "email": "reset-route@example.com",
                "password": "new-password"
            }
        )

    assert reset_request.status_code == 200
    assert reset_confirm.status_code == 200
    assert logged_in.status_code == 200


def test_admin_routes_require_admin_and_allow_user_updates(monkeypatch, tmp_path):
    configure_auth_routes(
        monkeypatch,
        tmp_path
    )
    user = main.user_store.create_user(
        email="normal@example.com",
        password="strong-password"
    )
    admin = main.user_store.create_user(
        email="admin@example.com",
        password="strong-password",
        role="admin",
        email_verified=True
    )
    user_token = main.token_service.create_token(
        user
    )
    admin_token = main.token_service.create_token(
        admin
    )

    with TestClient(
        main.app
    ) as client:
        forbidden = client.get(
            "/admin/users",
            headers={
                "Authorization": f"Bearer {user_token}"
            }
        )
        users = client.get(
            "/admin/users",
            headers={
                "Authorization": f"Bearer {admin_token}"
            }
        )
        updated = client.patch(
            f"/admin/users/{user.user_id}",
            json={
                "active": False,
                "email_verified": True
            },
            headers={
                "Authorization": f"Bearer {admin_token}"
            }
        )

    assert forbidden.status_code == 403
    assert users.status_code == 200
    assert len(users.json()["users"]) == 2
    assert updated.status_code == 200
    assert updated.json()["user"]["active"] is False
    assert updated.json()["user"]["email_verified"] is True


def test_metrics_and_observability_endpoints(monkeypatch, tmp_path):
    configure_auth_routes(
        monkeypatch,
        tmp_path
    )

    with TestClient(
        main.app
    ) as client:
        health = client.get(
            "/health"
        )
        metrics = client.get(
            "/metrics"
        )
        snapshot = client.get(
            "/observability"
        )
        dashboard = client.get(
            "/observability/dashboard"
        )

    assert health.status_code == 200
    assert metrics.status_code == 200
    assert "finintel_requests_total" in metrics.text
    assert snapshot.status_code == 200
    assert "recent_traces" in snapshot.json()
    assert dashboard.status_code == 200
    assert "FinIntel Observability" in dashboard.text


def test_uptime_monitor_head_requests(monkeypatch, tmp_path):
    configure_auth_routes(
        monkeypatch,
        tmp_path
    )

    with TestClient(
        main.app
    ) as client:
        root = client.head(
            "/"
        )
        health = client.head(
            "/health"
        )

    assert root.status_code == 200
    assert health.status_code == 200
    assert root.text == ""
    assert health.text == ""


def test_chat_history_requires_authentication(monkeypatch, tmp_path):
    configure_auth_routes(
        monkeypatch,
        tmp_path
    )

    with TestClient(
        main.app
    ) as client:
        response = client.get(
            "/chat/history"
        )

    assert response.status_code == 401


def test_chat_history_returns_principal_records(monkeypatch, tmp_path):
    configure_auth_routes(
        monkeypatch,
        tmp_path
    )
    user = main.user_store.create_user(
        email="history@example.com",
        password="strong-password"
    )
    token = main.token_service.create_token(
        user
    )
    main.chat_audit_store.record_chat(
        request_id="req-history",
        principal_id=f"user:{user.user_id}",
        user_id=user.user_id,
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
                "confidence_score": 0.9
            },
            "error": None
        },
        latency_ms=10
    )

    with TestClient(
        main.app
    ) as client:
        response = client.get(
            "/chat/history",
            headers={
                "Authorization": f"Bearer {token}"
            }
        )

    assert response.status_code == 200
    assert response.json()["history"][0]["query"] == "What is ROE?"
