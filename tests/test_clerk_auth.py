import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.config import settings
from backend.security.clerk_auth import ClerkAuthenticator


def test_clerk_authenticator_disabled_without_jwks_url():
    authenticator = ClerkAuthenticator(
        jwks_url="",
        issuer="",
        audience=""
    )

    assert authenticator.enabled is False
    assert authenticator.authenticate(
        "token"
    ) is None


def test_clerk_authenticator_requires_issuer():
    authenticator = ClerkAuthenticator(
        jwks_url="https://clerk.example.test/.well-known/jwks.json",
        issuer="",
        audience="",
    )

    assert authenticator.enabled is False


def test_clerk_authenticator_rejects_claims_without_subject(monkeypatch):
    authenticator = ClerkAuthenticator(
        jwks_url="https://clerk.example.test/.well-known/jwks.json",
        issuer="https://clerk.example.test",
        audience="",
    )
    monkeypatch.setattr(
        authenticator,
        "verify_token",
        lambda token: {"email": "missing-sub@example.com"},
    )

    assert authenticator.authenticate("token") is None


def test_required_settings_fail_closed_without_clerk(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setattr(settings, "CLERK_JWKS_URL", "")
    monkeypatch.setattr(settings, "CLERK_ISSUER", "")
    monkeypatch.setattr(
        settings,
        "AUDIT_DATABASE_PATH",
        str(tmp_path / "audit.sqlite3"),
    )
    monkeypatch.setattr(
        settings.MigrationRunner,
        "apply_pending",
        lambda self: [],
    )

    with pytest.raises(
        RuntimeError,
        match="CLERK_JWKS_URL, CLERK_ISSUER",
    ):
        settings.validate_required_settings()


def test_clerk_user_from_claims_maps_role_and_profile():
    user = ClerkAuthenticator.user_from_claims(
        {
            "sub": "user_123",
            "email": "clerk@example.com",
            "name": "Clerk User",
            "public_metadata": {
                "role": "admin"
            }
        }
    )

    assert user.user_id == "user_123"
    assert user.email == "clerk@example.com"
    assert user.full_name == "Clerk User"
    assert user.role == "admin"
    assert user.is_clerk is True


def test_auth_me_accepts_mocked_clerk_bearer(monkeypatch, tmp_path):
    class FakeClerkAuthenticator:
        def authenticate(self, token):
            return ClerkAuthenticator.user_from_claims(
                {
                    "sub": "user_clerk",
                    "email": "clerk@example.com",
                    "name": "Clerk User"
                }
            )

    monkeypatch.setattr(
        main,
        "clerk_authenticator",
        FakeClerkAuthenticator()
    )
    monkeypatch.setattr(
        main.settings,
        "validate_required_settings",
        lambda: None
    )

    with TestClient(
        main.app
    ) as client:
        response = client.get(
            "/auth/me",
            headers={
                "Authorization": "Bearer clerk-token"
            }
        )

    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == "user_clerk"
    assert response.json()["user"]["email"] == "clerk@example.com"


def test_chat_history_uses_clerk_principal(monkeypatch, tmp_path):
    class FakeClerkAuthenticator:
        def authenticate(self, token):
            return ClerkAuthenticator.user_from_claims(
                {
                    "sub": "user_clerk_history",
                    "email": "clerk-history@example.com",
                    "name": "Clerk History"
                }
            )

    monkeypatch.setattr(
        main,
        "clerk_authenticator",
        FakeClerkAuthenticator()
    )
    monkeypatch.setattr(
        main,
        "chat_audit_store",
        main.ChatAuditStore(
            database_path=str(tmp_path / "audit.sqlite3")
        )
    )
    monkeypatch.setattr(
        main.settings,
        "validate_required_settings",
        lambda: None
    )
    main.chat_audit_store.record_chat(
        request_id="req-clerk-history",
        principal_id="clerk:user_clerk_history",
        user_id=None,
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
                "Authorization": "Bearer clerk-token"
            }
        )

    assert response.status_code == 200
    assert response.json()["history"][0]["query"] == "What is ROE?"
