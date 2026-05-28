import re
import sqlite3
from pathlib import Path

from backend.storage.database import database_backend
from backend.storage.database import normalize_database_url
from backend.storage.database import resolve_sqlite_path


try:
    import psycopg
    from psycopg.rows import tuple_row
except Exception:  # pragma: no cover - exercised only without optional dep
    psycopg = None
    tuple_row = None


AUTOINCREMENT_TABLES = {
    "users",
    "auth_tokens",
    "chat_audit",
    "chat_messages"
}


class PostgresCursor:

    def __init__(
        self,
        cursor
    ):
        self.cursor = cursor
        self.lastrowid = None

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class PostgresConnection:

    def __init__(
        self,
        database_url: str
    ):
        if psycopg is None:
            raise RuntimeError(
                "psycopg is required for PostgreSQL DATABASE_URL support."
            )

        self.connection = psycopg.connect(
            normalize_database_url(
                database_url
            ),
            row_factory=tuple_row
        )

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback
    ):
        return self.connection.__exit__(
            exc_type,
            exc,
            traceback
        )

    def execute(
        self,
        statement: str,
        parameters=()
    ):
        translated = translate_sqlite_sql_to_postgres(
            statement
        )
        if isinstance(
            translated,
            tuple
        ):
            sql, translated_parameters = translated
            parameters = translated_parameters
        else:
            sql = translated

        sql = add_returning_id_if_needed(
            sql
        )
        cursor = self.connection.execute(
            sql,
            parameters
        )
        wrapper = PostgresCursor(
            cursor
        )

        if " RETURNING id" in sql:
            row = cursor.fetchone()
            wrapper.lastrowid = row[0] if row else None

        return wrapper


def add_returning_id_if_needed(
    statement: str
) -> str:

    normalized = " ".join(
        statement.strip().split()
    )

    if not normalized.upper().startswith(
        "INSERT INTO "
    ):
        return statement

    if " RETURNING " in normalized.upper():
        return statement

    match = re.match(
        r"INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        normalized,
        flags=re.IGNORECASE
    )

    if not match:
        return statement

    table = match.group(
        1
    )

    if table not in AUTOINCREMENT_TABLES:
        return statement

    return statement.rstrip().rstrip(";") + " RETURNING id"


def translate_sqlite_sql_to_postgres(
    statement: str
) -> str:

    stripped = statement.strip()
    pragma_match = re.match(
        r"PRAGMA\s+table_info\(([^)]+)\)",
        stripped,
        flags=re.IGNORECASE
    )

    if pragma_match:
        table = pragma_match.group(
            1
        ).strip("'\"")

        return (
            "SELECT ordinal_position - 1, column_name "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position"
        ), (
            table,
        )

    sql = statement
    sql = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "BIGSERIAL PRIMARY KEY",
        sql,
        flags=re.IGNORECASE
    )
    sql = re.sub(
        r"ALTER\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+ADD\s+COLUMN\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        r"ALTER TABLE \1 ADD COLUMN IF NOT EXISTS \2",
        sql,
        flags=re.IGNORECASE
    )
    sql = sql.replace(
        "strftime('%s', 'now')",
        "EXTRACT(EPOCH FROM now())::BIGINT"
    )
    sql = re.sub(
        r"\bINTEGER\b",
        "BIGINT",
        sql,
        flags=re.IGNORECASE
    )
    sql = re.sub(
        r"\bREAL\b",
        "DOUBLE PRECISION",
        sql,
        flags=re.IGNORECASE
    )
    sql = sql.replace(
        "?",
        "%s"
    )

    return sql


def connect_database(
    *,
    database_url: str | None = None,
    database_path: str | None = None
):

    if database_path:
        Path(database_path).parent.mkdir(
            parents=True,
            exist_ok=True
        )
        return sqlite3.connect(
            database_path
        )

    if not database_url:
        raise ValueError(
            "database_url or database_path is required."
        )

    backend = database_backend(
        database_url
    )

    if backend == "sqlite":
        database_path = resolve_sqlite_path(
            database_url
        )
        Path(database_path).parent.mkdir(
            parents=True,
            exist_ok=True
        )
        return sqlite3.connect(
            database_path
        )

    return PostgresConnection(
        database_url
    )
