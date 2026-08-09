import json
import time
from uuid import uuid4

from backend.config import settings
from backend.storage import connect_database


class ChatAuditStore:

    def __init__(
        self,
        database_path: str | None = None,
        database_url: str | None = None
    ):
        if database_path:
            self.database_path = database_path
            self.database_url = None
        elif database_url:
            self.database_path = None
            self.database_url = database_url
        else:
            self.database_path = settings.AUDIT_DATABASE_PATH
            self.database_url = settings.AUDIT_DATABASE_URL

        self.init_db()

    def connect(self):
        return connect_database(
            database_url=self.database_url,
            database_path=self.database_path
        )

    def init_db(self):
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_audit (
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
                """
                CREATE INDEX IF NOT EXISTS idx_chat_audit_principal_created
                ON chat_audit (principal_id, created_at DESC)
                """
            )

    @staticmethod
    def ensure_payload_columns(
        connection
    ):
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(chat_audit)"
            ).fetchall()
        }
        column_definitions = {
            "response_json": "TEXT",
            "answer_detail": "TEXT",
            "model": "TEXT",
            "conversation_id": "TEXT"
        }

        for column, column_type in column_definitions.items():
            if column in columns:
                continue

            connection.execute(
                f"ALTER TABLE chat_audit ADD COLUMN {column} {column_type}"
            )

    @staticmethod
    def to_json(
        value
    ) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str
        )

    @staticmethod
    def row_to_record(
        row
    ) -> dict:
        return {
            "id": row[0],
            "request_id": row[1],
            "principal_id": row[2],
            "user_id": row[3],
            "api_client_id": row[4],
            "query": row[5],
            "route": row[6],
            "routing": json.loads(row[7]) if row[7] else None,
            "query_intelligence": json.loads(row[8]) if row[8] else None,
            "response_success": bool(row[9]),
            "response_error": row[10],
            "response": json.loads(row[11]) if row[11] else None,
            "answer_detail": row[12],
            "model": row[13],
            "conversation_id": row[14],
            "confidence_score": row[15],
            "latency_ms": row[16],
            "created_at": row[17]
        }

    @staticmethod
    def message_row_to_record(
        row
    ) -> dict:
        return {
            "id": row[0],
            "conversation_id": row[1],
            "principal_id": row[2],
            "role": row[3],
            "content": row[4],
            "payload": json.loads(row[5]) if row[5] else None,
            "created_at": row[6]
        }

    @staticmethod
    def ensure_conversation_tables(
        connection
    ):
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_conversations (
                id TEXT PRIMARY KEY,
                principal_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_conversations_principal_updated
            ON chat_conversations (principal_id, updated_at DESC)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                payload_json TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created
            ON chat_messages (conversation_id, created_at ASC, id ASC)
            """
        )
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(chat_conversations)"
            ).fetchall()
        }
        if "pinned" not in columns:
            connection.execute(
                """
                ALTER TABLE chat_conversations
                ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0
                """
            )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_conversations_principal_pinned_updated
            ON chat_conversations (principal_id, pinned DESC, updated_at DESC)
            """
        )

    def record_chat(
        self,
        *,
        request_id: str,
        principal_id: str | None,
        user_id: int | None,
        api_client_id: str | None,
        query: str,
        route: str,
        routing: dict,
        query_intelligence: dict,
        response: dict,
        answer_detail: str | None = None,
        model: str | None = None,
        conversation_id: str | None = None,
        latency_ms: float | None = None
    ) -> int:
        response_success = bool(
            response.get(
                "success"
            )
        )
        response_error = response.get(
            "error"
        )
        payload = response.get(
            "data",
            {}
        ) or {}
        confidence_score = payload.get(
            "confidence_score"
        )

        with self.connect() as connection:
            self.ensure_payload_columns(
                connection
            )
            cursor = connection.execute(
                """
                INSERT INTO chat_audit (
                    request_id,
                    principal_id,
                    user_id,
                    api_client_id,
                    query,
                    route,
                    routing_json,
                    intelligence_json,
                    response_success,
                    response_error,
                    response_json,
                    answer_detail,
                    model,
                    conversation_id,
                    confidence_score,
                    latency_ms,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    principal_id,
                    user_id,
                    api_client_id,
                    query,
                    route,
                    self.to_json(routing),
                    self.to_json(query_intelligence),
                    1 if response_success else 0,
                    response_error,
                    self.to_json(response),
                    answer_detail,
                    model,
                    conversation_id,
                    confidence_score,
                    latency_ms,
                    int(time.time())
                )
            )

            return int(
                cursor.lastrowid
            )

    def list_for_principal(
        self,
        principal_id: str,
        limit: int = 25
    ) -> list[dict]:
        bounded_limit = max(
            1,
            min(
                int(limit),
                100
            )
        )

        with self.connect() as connection:
            self.ensure_payload_columns(
                connection
            )
            rows = connection.execute(
                """
                SELECT
                    id,
                    request_id,
                    principal_id,
                    user_id,
                    api_client_id,
                    query,
                    route,
                    routing_json,
                    intelligence_json,
                    response_success,
                    response_error,
                    response_json,
                    answer_detail,
                    model,
                    conversation_id,
                    confidence_score,
                    latency_ms,
                    created_at
                FROM chat_audit
                WHERE principal_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (
                    principal_id,
                    bounded_limit
                )
            ).fetchall()

        return [
            self.row_to_record(row)
            for row in rows
        ]

    def create_conversation(
        self,
        *,
        principal_id: str,
        title: str
    ) -> str:
        conversation_id = str(
            uuid4()
        )
        now = int(
            time.time()
        )
        clean_title = (
            title.strip()[:120]
            or "New research chat"
        )

        with self.connect() as connection:
            self.ensure_conversation_tables(
                connection
            )
            connection.execute(
                """
                INSERT INTO chat_conversations (
                    id,
                    principal_id,
                    title,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    principal_id,
                    clean_title,
                    now,
                    now
                )
            )

        return conversation_id

    def conversation_exists(
        self,
        *,
        principal_id: str,
        conversation_id: str
    ) -> bool:
        with self.connect() as connection:
            self.ensure_conversation_tables(
                connection
            )
            row = connection.execute(
                """
                SELECT 1
                FROM chat_conversations
                WHERE id = ? AND principal_id = ?
                """,
                (
                    conversation_id,
                    principal_id
                )
            ).fetchone()

        return bool(
            row
        )

    def touch_conversation(
        self,
        *,
        principal_id: str,
        conversation_id: str
    ):
        with self.connect() as connection:
            self.ensure_conversation_tables(
                connection
            )
            connection.execute(
                """
                UPDATE chat_conversations
                SET updated_at = ?
                WHERE id = ? AND principal_id = ?
                """,
                (
                    int(time.time()),
                    conversation_id,
                    principal_id
                )
            )

    def rename_conversation(
        self,
        *,
        principal_id: str,
        conversation_id: str,
        title: str
    ) -> bool:
        clean_title = title.strip()[:120]
        if not clean_title:
            return False

        with self.connect() as connection:
            self.ensure_conversation_tables(
                connection
            )
            existing = connection.execute(
                """
                SELECT 1
                FROM chat_conversations
                WHERE id = ? AND principal_id = ?
                """,
                (
                    conversation_id,
                    principal_id
                )
            ).fetchone()
            if not existing:
                return False

            connection.execute(
                """
                UPDATE chat_conversations
                SET title = ?, updated_at = ?
                WHERE id = ? AND principal_id = ?
                """,
                (
                    clean_title,
                    int(time.time()),
                    conversation_id,
                    principal_id
                )
            )

        return True

    def set_conversation_pinned(
        self,
        *,
        principal_id: str,
        conversation_id: str,
        pinned: bool
    ) -> bool:
        with self.connect() as connection:
            self.ensure_conversation_tables(
                connection
            )
            existing = connection.execute(
                """
                SELECT 1
                FROM chat_conversations
                WHERE id = ? AND principal_id = ?
                """,
                (
                    conversation_id,
                    principal_id
                )
            ).fetchone()
            if not existing:
                return False

            connection.execute(
                """
                UPDATE chat_conversations
                SET pinned = ?
                WHERE id = ? AND principal_id = ?
                """,
                (
                    1 if pinned else 0,
                    conversation_id,
                    principal_id
                )
            )

        return True

    def delete_conversation(
        self,
        *,
        principal_id: str,
        conversation_id: str
    ) -> bool:
        with self.connect() as connection:
            self.ensure_conversation_tables(
                connection
            )
            existing = connection.execute(
                """
                SELECT 1
                FROM chat_conversations
                WHERE id = ? AND principal_id = ?
                """,
                (
                    conversation_id,
                    principal_id
                )
            ).fetchone()
            if not existing:
                return False

            connection.execute(
                """
                DELETE FROM chat_messages
                WHERE conversation_id = ? AND principal_id = ?
                """,
                (
                    conversation_id,
                    principal_id
                )
            )
            connection.execute(
                """
                DELETE FROM chat_conversations
                WHERE id = ? AND principal_id = ?
                """,
                (
                    conversation_id,
                    principal_id
                )
            )

        return True

    def add_message(
        self,
        *,
        conversation_id: str,
        principal_id: str,
        role: str,
        content: str,
        payload: dict | None = None
    ) -> int:
        now = int(
            time.time()
        )

        with self.connect() as connection:
            self.ensure_conversation_tables(
                connection
            )
            cursor = connection.execute(
                """
                INSERT INTO chat_messages (
                    conversation_id,
                    principal_id,
                    role,
                    content,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    principal_id,
                    role,
                    content,
                    self.to_json(payload) if payload else None,
                    now
                )
            )
            connection.execute(
                """
                UPDATE chat_conversations
                SET updated_at = ?
                WHERE id = ? AND principal_id = ?
                """,
                (
                    now,
                    conversation_id,
                    principal_id
                )
            )

            return int(
                cursor.lastrowid
            )

    def list_conversations(
        self,
        principal_id: str,
        limit: int = 25,
        offset: int = 0,
        search: str = ""
    ) -> list[dict]:
        bounded_limit = max(
            1,
            min(
                int(limit),
                100
            )
        )
        bounded_offset = max(
            0,
            int(offset)
        )
        clean_search = search.strip().lower()[:120]

        with self.connect() as connection:
            self.ensure_conversation_tables(
                connection
            )
            if clean_search:
                rows = connection.execute(
                    """
                    SELECT
                        id,
                        title,
                        created_at,
                        updated_at,
                        pinned
                    FROM chat_conversations
                    WHERE principal_id = ? AND LOWER(title) LIKE ?
                    ORDER BY pinned DESC, updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (
                        principal_id,
                        f"%{clean_search}%",
                        bounded_limit,
                        bounded_offset
                    )
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        id,
                        title,
                        created_at,
                        updated_at,
                        pinned
                    FROM chat_conversations
                    WHERE principal_id = ?
                    ORDER BY pinned DESC, updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (
                        principal_id,
                        bounded_limit,
                        bounded_offset
                    )
                ).fetchall()

        return [
            {
                "conversation_id": row[0],
                "title": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "pinned": bool(row[4])
            }
            for row in rows
        ]

    def list_messages(
        self,
        *,
        principal_id: str,
        conversation_id: str
    ) -> list[dict]:
        with self.connect() as connection:
            self.ensure_conversation_tables(
                connection
            )
            rows = connection.execute(
                """
                SELECT
                    id,
                    conversation_id,
                    principal_id,
                    role,
                    content,
                    payload_json,
                    created_at
                FROM chat_messages
                WHERE principal_id = ? AND conversation_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (
                    principal_id,
                    conversation_id
                )
            ).fetchall()

        return [
            self.message_row_to_record(row)
            for row in rows
        ]
