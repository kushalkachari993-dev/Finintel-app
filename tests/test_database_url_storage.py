import pytest
from pathlib import Path

from backend.audit import ChatAuditStore
from backend.security.user_auth import UserStore
from backend.storage import resolve_sqlite_path


def test_resolve_sqlite_database_url_to_path():
    resolved = Path(
        resolve_sqlite_path(
            "sqlite:///data/finintel.sqlite3"
        )
    )

    assert resolved.parts[-2:] == (
        "data",
        "finintel.sqlite3"
    )


def test_rejects_unsupported_database_url():
    with pytest.raises(
        ValueError
    ):
        resolve_sqlite_path(
            "postgresql://user:pass@example.com/db"
        )


def test_user_and_audit_stores_can_share_database_url(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'finintel.sqlite3').as_posix()}"

    user_store = UserStore(
        database_url=database_url
    )
    audit_store = ChatAuditStore(
        database_url=database_url
    )

    user = user_store.create_user(
        email="shared@example.com",
        password="strong-password",
        full_name="Shared User"
    )
    audit_store.record_chat(
        request_id="req-shared",
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
        latency_ms=12.0
    )

    assert user_store.get_user_by_email(
        "shared@example.com"
    )
    assert audit_store.list_for_principal(
        f"user:{user.user_id}"
    )[0]["query"] == "What is ROE?"
