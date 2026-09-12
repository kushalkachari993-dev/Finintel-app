import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.audit import ChatAuditStore
from backend.storage import PostgresConversationRepository
from backend.storage import ConversationRepositoryError
from backend.storage import MigrationRunner
from backend.storage import ThreadedConversationRepository
from backend.storage import build_conversation_repository
from backend.storage.migrations import list_migrations


@pytest.mark.anyio
async def test_threaded_repository_is_not_ready_until_migrations_run(tmp_path):
    database_path = str(tmp_path / "unmigrated.sqlite3")
    store = ChatAuditStore(database_path=database_path)
    repository = ThreadedConversationRepository(
        lambda: store,
        operation_timeout_seconds=5,
    )

    assert await repository.ready() is False

    MigrationRunner(database_path=database_path).apply_pending()

    assert await repository.ready() is True


@pytest.mark.anyio
async def test_threaded_repository_persists_research_result_atomically(tmp_path):
    database_path = str(tmp_path / "repository.sqlite3")
    MigrationRunner(database_path=database_path).apply_pending()
    store = ChatAuditStore(database_path=database_path)
    repository = ThreadedConversationRepository(
        lambda: store,
        operation_timeout_seconds=5,
    )

    assert await repository.ready() is True
    conversation_id = await repository.create_conversation(
        principal_id="clerk:user_1",
        title="HDFC Bank",
    )
    await repository.add_message(
        conversation_id=conversation_id,
        principal_id="clerk:user_1",
        role="user",
        content="Analyze HDFC Bank",
    )
    message_id, audit_id = await repository.persist_assistant_and_audit(
        conversation_id=conversation_id,
        principal_id="clerk:user_1",
        content="Analysis completed.",
        payload={"success": True, "response": {"success": True}},
        request_id="req-1",
        user_id=None,
        api_client_id=None,
        query="Analyze HDFC Bank",
        route="FUNDAMENTAL",
        routing={"route": "FUNDAMENTAL"},
        query_intelligence={"companies": ["HDFC Bank"]},
        response={
            "success": True,
            "data": {"confidence_score": 0.9},
            "error": None,
        },
        answer_detail="brief",
        model="test-model",
        latency_ms=12.5,
    )

    messages = await repository.list_messages(
        principal_id="clerk:user_1",
        conversation_id=conversation_id,
    )
    history = await repository.list_for_principal("clerk:user_1")

    assert message_id > 0
    assert audit_id > 0
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert history[0]["conversation_id"] == conversation_id


@pytest.mark.anyio
async def test_repository_hides_driver_error_details():
    class BrokenStore:
        def list_messages(self, **kwargs):
            raise RuntimeError(
                "connection to secret-db.example.test failed for admin"
            )

    repository = ThreadedConversationRepository(
        lambda: BrokenStore(),
        operation_timeout_seconds=5,
    )

    with pytest.raises(
        ConversationRepositoryError,
        match="Database operation failed",
    ) as error:
        await repository.list_messages(
            principal_id="clerk:user_1",
            conversation_id="conversation-1",
        )

    assert "secret-db" not in str(error.value)


def test_sqlite_atomic_persistence_rolls_back_both_records(
    monkeypatch,
    tmp_path,
):
    database_path = str(tmp_path / "rollback.sqlite3")
    MigrationRunner(database_path=database_path).apply_pending()
    store = ChatAuditStore(database_path=database_path)
    conversation_id = store.create_conversation(
        principal_id="clerk:user_1",
        title="Rollback",
    )

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(store, "_insert_chat_audit", fail_audit)

    with pytest.raises(RuntimeError, match="audit insert failed"):
        store.persist_assistant_and_audit(
            conversation_id=conversation_id,
            principal_id="clerk:user_1",
            content="Must roll back",
            payload={"success": False},
            request_id="req-rollback",
            user_id=None,
            api_client_id=None,
            query="Rollback",
            route="FUNDAMENTAL",
            routing={},
            query_intelligence={},
            response={"success": False, "error": "failed"},
        )

    assert store.list_messages(
        principal_id="clerk:user_1",
        conversation_id=conversation_id,
    ) == []
    assert store.list_for_principal("clerk:user_1") == []


def test_repository_factory_uses_postgres_pool_for_neon_url():
    repository = build_conversation_repository(
        database_url="postgresql://user:secret@example.test/neondb",
        database_path=None,
        store_provider=lambda: None,
        min_pool_size=1,
        max_pool_size=5,
        pool_timeout_seconds=10,
        operation_timeout_seconds=10,
        connect_retries=3,
        retry_delay_seconds=1,
    )

    assert isinstance(repository, PostgresConversationRepository)
    assert repository.pool is None


@pytest.mark.anyio
async def test_postgres_pool_start_retries_and_closes(monkeypatch):
    class FakeCursor:
        def __init__(self, rows):
            self.rows = rows

        async def fetchone(self):
            return self.rows[0] if self.rows else None

        async def fetchall(self):
            return self.rows

    class FakeConnection:
        async def execute(self, statement):
            if statement == "SELECT 1":
                return FakeCursor([(1,)])
            assert statement == (
                "SELECT version, checksum FROM schema_migrations"
            )
            return FakeCursor(
                [
                    (migration.version, migration.checksum)
                    for migration in list_migrations()
                ]
            )

    class ConnectionContext:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class FakePool:
        def __init__(self, fail=False):
            self.fail = fail
            self.closed = False

        async def open(self, **kwargs):
            if self.fail:
                raise ConnectionError("temporary failure")

        def connection(self, **kwargs):
            return ConnectionContext()

        async def close(self, **kwargs):
            self.closed = True

    repository = PostgresConversationRepository(
        "postgresql://user:secret@example.test/neondb",
        min_pool_size=1,
        max_pool_size=5,
        pool_timeout_seconds=10,
        operation_timeout_seconds=10,
        connect_retries=2,
        retry_delay_seconds=0,
    )
    failed_pool = FakePool(fail=True)
    working_pool = FakePool()
    pools = iter([failed_pool, working_pool])
    monkeypatch.setattr(repository, "_new_pool", lambda: next(pools))

    await repository.start()

    assert failed_pool.closed is True
    assert repository.pool is working_pool
    await repository.close()
    assert working_pool.closed is True
    assert repository.pool is None


def test_ready_endpoint_reports_database_readiness(monkeypatch):
    class FakeRepository:
        async def start(self):
            return None

        async def close(self):
            return None

        async def ready(self):
            return True

    monkeypatch.setattr(main, "conversation_repository", FakeRepository())
    monkeypatch.setattr(
        main.settings,
        "validate_required_settings",
        lambda: None,
    )

    with TestClient(main.app) as client:
        ready = client.get("/ready")
        health = client.get("/health")

    assert ready.status_code == 200
    assert ready.json() == {"status": "ok", "database": "ready"}
    assert health.status_code == 200


def test_ready_endpoint_returns_503_when_database_is_unavailable(monkeypatch):
    class FakeRepository:
        async def start(self):
            return None

        async def close(self):
            return None

        async def ready(self):
            return False

    monkeypatch.setattr(main, "conversation_repository", FakeRepository())
    monkeypatch.setattr(
        main.settings,
        "validate_required_settings",
        lambda: None,
    )

    with TestClient(main.app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
    }
