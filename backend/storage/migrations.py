import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from backend.storage.connection import connect_database
from backend.storage.database import database_backend


MIGRATIONS_DIR = Path(__file__).with_name("migrations")
POSTGRES_MIGRATION_LOCK_ID = int.from_bytes(b"FININTEL", "big")


class MigrationStateError(RuntimeError):
    pass


class MigrationChecksumError(MigrationStateError):
    pass


class SchemaNotCurrentError(MigrationStateError):
    pass


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    checksum: str


@dataclass(frozen=True)
class SchemaStatus:
    metadata_current: bool
    expected_versions: tuple[str, ...]
    applied_versions: tuple[str, ...]
    pending_versions: tuple[str, ...]
    unexpected_versions: tuple[str, ...]
    checksum_mismatches: tuple[str, ...]

    @property
    def current(self) -> bool:
        return (
            self.metadata_current
            and not self.pending_versions
            and not self.unexpected_versions
            and not self.checksum_mismatches
        )

    def as_dict(self) -> dict:
        return {
            "current": self.current,
            "metadata_current": self.metadata_current,
            "expected_versions": list(self.expected_versions),
            "applied_versions": list(self.applied_versions),
            "pending_versions": list(self.pending_versions),
            "unexpected_versions": list(self.unexpected_versions),
            "checksum_mismatches": list(self.checksum_mismatches),
        }


def migration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def list_migrations(
    migrations_dir: Path = MIGRATIONS_DIR,
) -> list[Migration]:
    if not migrations_dir.exists():
        return []

    migrations = []
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.name.split("_", 1)[0]
        if not version.isdigit():
            continue
        migrations.append(
            Migration(
                version=version,
                path=path,
                checksum=migration_checksum(path),
            )
        )
    return migrations


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL without breaking on semicolons inside quoted values."""
    statements = []
    buffer = []
    for character in sql:
        buffer.append(character)
        if character != ";":
            continue
        candidate = "".join(buffer).strip()
        if not sqlite3.complete_statement(candidate):
            continue
        statement = candidate[:-1].strip()
        if statement:
            statements.append(statement)
        buffer = []

    remainder = "".join(buffer).strip()
    if remainder:
        raise MigrationStateError(
            "Migration SQL must terminate every statement with a semicolon."
        )
    return statements


def schema_status_from_rows(
    rows,
    migrations: list[Migration],
    *,
    metadata_current: bool = True,
) -> SchemaStatus:
    expected = {migration.version: migration.checksum for migration in migrations}
    applied = {str(row[0]): row[1] for row in rows}
    return SchemaStatus(
        metadata_current=metadata_current,
        expected_versions=tuple(expected),
        applied_versions=tuple(sorted(applied)),
        pending_versions=tuple(
            version for version in expected if version not in applied
        ),
        unexpected_versions=tuple(
            version for version in sorted(applied) if version not in expected
        ),
        checksum_mismatches=tuple(
            version
            for version, checksum in expected.items()
            if version in applied and applied[version] != checksum
        ),
    )


class MigrationRunner:
    def __init__(
        self,
        database_path: str | None = None,
        database_url: str | None = None,
        migrations_dir: Path = MIGRATIONS_DIR,
    ):
        self.database_path = database_path
        self.database_url = database_url
        self.migrations_dir = migrations_dir

    @property
    def backend(self) -> str:
        if self.database_path:
            return "sqlite"
        if not self.database_url:
            raise ValueError("database_url or database_path is required.")
        return database_backend(self.database_url)

    @property
    def migrations(self) -> list[Migration]:
        return list_migrations(self.migrations_dir)

    def connect(self, *, read_only: bool = False):
        return connect_database(
            database_url=self.database_url,
            database_path=self.database_path,
            read_only=read_only,
        )

    @staticmethod
    def ensure_schema_migrations_table(connection):
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                checksum TEXT,
                applied_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
            """
        )
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(schema_migrations)"
            ).fetchall()
        }
        if "checksum" not in columns:
            connection.execute(
                "ALTER TABLE schema_migrations ADD COLUMN checksum TEXT"
            )

    @staticmethod
    def applied_migrations(connection) -> dict[str, str | None]:
        rows = connection.execute(
            "SELECT version, checksum FROM schema_migrations"
        ).fetchall()
        return {str(row[0]): row[1] for row in rows}

    @staticmethod
    def _begin_transaction(connection, backend: str):
        statement = "BEGIN IMMEDIATE" if backend == "sqlite" else "BEGIN"
        connection.execute(statement)

    @staticmethod
    def _column_exists(connection, table: str, column: str) -> bool:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        return column in {row[1] for row in rows}

    @classmethod
    def _is_verified_duplicate_column(
        cls,
        connection,
        statement: str,
        error: Exception,
    ) -> bool:
        if "duplicate column name" not in str(error).lower():
            return False
        match = re.match(
            r"ALTER\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s+"
            r"ADD\s+COLUMN\s+([A-Za-z_][A-Za-z0-9_]*)",
            " ".join(statement.split()),
            flags=re.IGNORECASE,
        )
        return bool(
            match
            and cls._column_exists(
                connection,
                match.group(1),
                match.group(2),
            )
        )

    @classmethod
    def execute_migration_sql(cls, connection, sql: str):
        for statement in split_sql_statements(sql):
            try:
                connection.execute(statement)
            except Exception as error:
                if cls._is_verified_duplicate_column(
                    connection,
                    statement,
                    error,
                ):
                    continue
                raise

    def _acquire_migration_lock(self, connection):
        if self.backend == "postgres":
            connection.execute(
                "SELECT pg_advisory_lock(?)",
                (POSTGRES_MIGRATION_LOCK_ID,),
            ).fetchone()

    def _release_migration_lock(self, connection):
        if self.backend == "postgres":
            connection.execute(
                "SELECT pg_advisory_unlock(?)",
                (POSTGRES_MIGRATION_LOCK_ID,),
            ).fetchone()

    @staticmethod
    def _commit(connection):
        connection.commit()

    @staticmethod
    def _rollback(connection):
        connection.rollback()

    def _validate_applied_state(
        self,
        connection,
        migrations: list[Migration],
    ) -> dict[str, str | None]:
        expected = {migration.version: migration for migration in migrations}
        applied = self.applied_migrations(connection)
        unexpected = sorted(set(applied) - set(expected))
        if unexpected:
            raise MigrationStateError(
                "Database contains unknown migration versions: "
                + ", ".join(unexpected)
            )

        mismatches = [
            version
            for version, checksum in applied.items()
            if checksum is not None
            and checksum != expected[version].checksum
        ]
        if mismatches:
            raise MigrationChecksumError(
                "Migration checksum mismatch for version(s): "
                + ", ".join(mismatches)
            )

        for version, checksum in applied.items():
            if checksum is not None:
                continue
            connection.execute(
                """
                UPDATE schema_migrations SET checksum = ?
                WHERE version = ?
                """,
                (expected[version].checksum, version),
            )
            applied[version] = expected[version].checksum
        return applied

    def apply_pending(self) -> list[str]:
        applied_versions = []
        migrations = self.migrations
        with self.connect() as connection:
            self._acquire_migration_lock(connection)
            try:
                self.ensure_schema_migrations_table(connection)
                applied = self._validate_applied_state(
                    connection,
                    migrations,
                )
                self._commit(connection)

                for migration in migrations:
                    if migration.version in applied:
                        continue
                    self._begin_transaction(connection, self.backend)
                    try:
                        self.execute_migration_sql(
                            connection,
                            migration.path.read_text(encoding="utf-8"),
                        )
                        connection.execute(
                            """
                            INSERT INTO schema_migrations (version, checksum)
                            VALUES (?, ?)
                            """,
                            (migration.version, migration.checksum),
                        )
                        self._commit(connection)
                    except Exception:
                        self._rollback(connection)
                        raise
                    applied_versions.append(migration.version)
            except Exception:
                self._rollback(connection)
                raise
            finally:
                self._release_migration_lock(connection)
                self._commit(connection)
        return applied_versions

    def schema_status(self, connection=None) -> SchemaStatus:
        migrations = self.migrations
        owns_connection = connection is None
        active_connection = connection
        try:
            if active_connection is None:
                active_connection = self.connect(read_only=True)
            rows = active_connection.execute(
                "SELECT version, checksum FROM schema_migrations"
            ).fetchall()
            return schema_status_from_rows(rows, migrations)
        except Exception:
            return schema_status_from_rows(
                [],
                migrations,
                metadata_current=False,
            )
        finally:
            if owns_connection and active_connection is not None:
                active_connection.close()

    def validate_current(self) -> SchemaStatus:
        status = self.schema_status()
        if not status.current:
            details = []
            if not status.metadata_current:
                details.append("migration metadata is missing or outdated")
            if status.pending_versions:
                details.append(
                    "pending=" + ",".join(status.pending_versions)
                )
            if status.unexpected_versions:
                details.append(
                    "unexpected=" + ",".join(status.unexpected_versions)
                )
            if status.checksum_mismatches:
                details.append(
                    "checksum_mismatch="
                    + ",".join(status.checksum_mismatches)
                )
            raise SchemaNotCurrentError(
                "Database schema is not current (" + "; ".join(details) + ")."
            )
        return status
