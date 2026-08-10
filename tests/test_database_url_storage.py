import pytest
from pathlib import Path

from backend.audit import ChatAuditStore
from backend.storage import database_backend
from backend.storage import normalize_database_url
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


def test_detects_and_normalizes_postgres_database_url():

    assert database_backend(
        "postgres://user:pass@example.com/db"
    ) == "postgres"
    assert normalize_database_url(
        "postgres://user:pass@example.com/db"
    ).startswith(
        "postgresql://"
    )


def test_audit_store_uses_database_url_for_clerk_principals(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'finintel.sqlite3').as_posix()}"

    audit_store = ChatAuditStore(
        database_url=database_url
    )

    audit_store.record_chat(
        request_id="req-shared",
        principal_id="clerk:user_shared",
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
        latency_ms=12.0
    )

    assert audit_store.list_for_principal(
        "clerk:user_shared"
    )[0]["query"] == "What is ROE?"
