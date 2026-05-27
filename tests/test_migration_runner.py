import sqlite3

from backend.storage.migrations import MigrationRunner
from backend.audit import ChatAuditStore


def table_names(database_path):
    with sqlite3.connect(
        database_path
    ) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

    return {
        row[0]
        for row in rows
    }


def migration_versions(database_path):
    with sqlite3.connect(
        database_path
    ) as connection:
        rows = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

    return [
        row[0]
        for row in rows
    ]


def table_columns(database_path, table_name):
    with sqlite3.connect(
        database_path
    ) as connection:
        rows = connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

    return {
        row[1]
        for row in rows
    }


def test_migration_runner_creates_core_schema(tmp_path):
    database_path = str(
        tmp_path / "finintel.sqlite3"
    )

    applied = MigrationRunner(
        database_path
    ).apply_pending()

    assert applied == [
        "001",
        "002",
        "003",
        "004",
        "005"
    ]
    assert {
        "schema_migrations",
        "users",
        "chat_audit",
        "chat_conversations",
        "chat_messages",
        "auth_tokens"
    }.issubset(
        table_names(database_path)
    )
    assert {
        "email_verified",
        "updated_at"
    }.issubset(
        table_columns(
            database_path,
            "users"
        )
    )
    assert {
        "response_json",
        "answer_detail",
        "model"
    }.issubset(
        table_columns(
            database_path,
            "chat_audit"
        )
    )
    assert migration_versions(database_path) == [
        "001",
        "002",
        "003",
        "004",
        "005"
    ]


def test_migration_runner_is_idempotent(tmp_path):
    database_path = str(
        tmp_path / "finintel.sqlite3"
    )
    runner = MigrationRunner(
        database_path
    )

    assert runner.apply_pending() == [
        "001",
        "002",
        "003",
        "004",
        "005"
    ]
    assert runner.apply_pending() == []
    assert migration_versions(database_path) == [
        "001",
        "002",
        "003",
        "004",
        "005"
    ]


def test_migration_runner_handles_precreated_audit_table(tmp_path):
    database_path = str(
        tmp_path / "finintel.sqlite3"
    )

    ChatAuditStore(
        database_path=database_path
    )

    applied = MigrationRunner(
        database_path
    ).apply_pending()

    assert applied == [
        "001",
        "002",
        "003",
        "004",
        "005"
    ]
    assert {
        "response_json",
        "answer_detail",
        "model",
        "conversation_id"
    }.issubset(
        table_columns(
            database_path,
            "chat_audit"
        )
    )
