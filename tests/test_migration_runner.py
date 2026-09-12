import sqlite3
from pathlib import Path

import pytest

from backend.storage.migrations import MigrationRunner
from backend.storage.migrations import MigrationChecksumError
from backend.storage.migrations import POSTGRES_MIGRATION_LOCK_ID
from backend.storage.migrations import SchemaNotCurrentError
from backend.storage.migrations import split_sql_statements


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


def migration_records(database_path):
    with sqlite3.connect(database_path) as connection:
        return connection.execute(
            """
            SELECT version, checksum
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()


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
        "005",
        "006"
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
    assert "pinned" in table_columns(
        database_path,
        "chat_conversations"
    )
    assert migration_versions(database_path) == [
        "001",
        "002",
        "003",
        "004",
        "005",
        "006"
    ]
    assert all(
        len(checksum) == 64
        for _, checksum in migration_records(database_path)
    )


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
        "005",
        "006"
    ]
    assert runner.apply_pending() == []
    assert migration_versions(database_path) == [
        "001",
        "002",
        "003",
        "004",
        "005",
        "006"
    ]


def test_migration_runner_handles_precreated_audit_table(tmp_path):
    database_path = str(
        tmp_path / "finintel.sqlite3"
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE chat_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                principal_id TEXT,
                user_id INTEGER,
                api_client_id TEXT,
                query TEXT NOT NULL,
                route TEXT,
                routing_json TEXT,
                intelligence_json TEXT,
                response_success INTEGER NOT NULL,
                response_error TEXT,
                confidence_score REAL,
                latency_ms REAL,
                created_at INTEGER NOT NULL
            )
            """
        )

    applied = MigrationRunner(
        database_path
    ).apply_pending()

    assert applied == [
        "001",
        "002",
        "003",
        "004",
        "005",
        "006"
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


def test_migration_runner_handles_partially_upgraded_audit_table(tmp_path):
    database_path = str(
        tmp_path / "finintel.sqlite3"
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE chat_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                principal_id TEXT,
                user_id INTEGER,
                api_client_id TEXT,
                query TEXT NOT NULL,
                route TEXT,
                routing_json TEXT,
                intelligence_json TEXT,
                response_success INTEGER NOT NULL,
                response_error TEXT,
                confidence_score REAL,
                latency_ms REAL,
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "ALTER TABLE chat_audit ADD COLUMN response_json TEXT"
        )
        connection.execute(
            "ALTER TABLE chat_audit ADD COLUMN answer_detail TEXT"
        )
        connection.execute(
            "ALTER TABLE chat_audit ADD COLUMN model TEXT"
        )

    applied = MigrationRunner(
        database_path
    ).apply_pending()

    assert applied == [
        "001",
        "002",
        "003",
        "004",
        "005",
        "006"
    ]
    assert migration_versions(database_path) == [
        "001",
        "002",
        "003",
        "004",
        "005",
        "006"
    ]


def test_schema_validation_is_read_only_and_detects_pending_migrations(
    tmp_path,
):
    database_path = str(tmp_path / "finintel.sqlite3")
    runner = MigrationRunner(database_path=database_path)

    with pytest.raises(SchemaNotCurrentError, match="schema is not current"):
        runner.validate_current()

    assert not Path(database_path).exists()
    assert runner.schema_status().current is False
    runner.apply_pending()
    assert runner.validate_current().current is True


def test_migration_checksum_change_is_rejected(tmp_path):
    database_path = str(tmp_path / "finintel.sqlite3")
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    migration_path = migrations_dir / "001_create_example.sql"
    migration_path.write_text(
        "CREATE TABLE example (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    runner = MigrationRunner(
        database_path=database_path,
        migrations_dir=migrations_dir,
    )
    runner.apply_pending()
    migration_path.write_text(
        "CREATE TABLE example (id INTEGER PRIMARY KEY, name TEXT);",
        encoding="utf-8",
    )

    with pytest.raises(MigrationChecksumError, match="001"):
        runner.apply_pending()
    assert runner.schema_status().checksum_mismatches == ("001",)


def test_existing_migration_metadata_receives_checksums(tmp_path):
    database_path = str(tmp_path / "finintel.sqlite3")
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_create_example.sql").write_text(
        "CREATE TABLE example (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES ('001', 1)"
        )
        connection.execute(
            "CREATE TABLE example (id INTEGER PRIMARY KEY)"
        )

    runner = MigrationRunner(
        database_path=database_path,
        migrations_dir=migrations_dir,
    )

    assert runner.apply_pending() == []
    assert len(migration_records(database_path)[0][1]) == 64
    assert runner.validate_current().current is True


def test_failed_migration_rolls_back_schema_and_version(tmp_path):
    database_path = str(tmp_path / "finintel.sqlite3")
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_broken.sql").write_text(
        """
        CREATE TABLE should_rollback (id INTEGER PRIMARY KEY);
        INSERT INTO table_that_does_not_exist (id) VALUES (1);
        """,
        encoding="utf-8",
    )
    runner = MigrationRunner(
        database_path=database_path,
        migrations_dir=migrations_dir,
    )

    with pytest.raises(sqlite3.OperationalError):
        runner.apply_pending()

    assert "should_rollback" not in table_names(database_path)
    assert migration_versions(database_path) == []


def test_sql_splitter_preserves_semicolons_inside_values():
    statements = split_sql_statements(
        """
        CREATE TABLE example (value TEXT);
        INSERT INTO example (value) VALUES ('one;two');
        """
    )

    assert len(statements) == 2
    assert "one;two" in statements[1]


def test_postgres_migrations_use_a_session_advisory_lock():
    class Cursor:
        @staticmethod
        def fetchone():
            return (True,)

    class Connection:
        def __init__(self):
            self.calls = []

        def execute(self, statement, parameters=()):
            self.calls.append((statement, parameters))
            return Cursor()

    runner = MigrationRunner(
        database_url="postgresql://user:secret@example.test/neondb"
    )
    connection = Connection()

    runner._acquire_migration_lock(connection)
    runner._release_migration_lock(connection)

    assert connection.calls == [
        (
            "SELECT pg_advisory_lock(?)",
            (POSTGRES_MIGRATION_LOCK_ID,),
        ),
        (
            "SELECT pg_advisory_unlock(?)",
            (POSTGRES_MIGRATION_LOCK_ID,),
        ),
    ]
