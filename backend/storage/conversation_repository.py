import asyncio
import json
import logging
import time
from collections.abc import Callable
from collections.abc import Coroutine
from typing import Any
from typing import Protocol
from uuid import uuid4

from backend.observability import observability
from backend.storage.database import database_backend
from backend.storage.database import normalize_database_url


logger = logging.getLogger(__name__)


try:
    from psycopg.rows import tuple_row
    from psycopg_pool import AsyncConnectionPool
except Exception:  # pragma: no cover - optional for SQLite development
    tuple_row = None
    AsyncConnectionPool = None


class ConversationRepositoryError(RuntimeError):
    """Sanitized persistence failure safe to return across service boundaries."""


class ConversationRepositoryTimeout(ConversationRepositoryError):
    pass


class ConversationRepository(Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...

    async def ready(self) -> bool: ...

    async def list_for_principal(
        self,
        principal_id: str,
        limit: int = 25,
    ) -> list[dict]: ...

    async def create_conversation(
        self,
        *,
        principal_id: str,
        title: str,
    ) -> str: ...

    async def conversation_exists(
        self,
        *,
        principal_id: str,
        conversation_id: str,
    ) -> bool: ...

    async def rename_conversation(
        self,
        *,
        principal_id: str,
        conversation_id: str,
        title: str,
    ) -> bool: ...

    async def set_conversation_pinned(
        self,
        *,
        principal_id: str,
        conversation_id: str,
        pinned: bool,
    ) -> bool: ...

    async def delete_conversation(
        self,
        *,
        principal_id: str,
        conversation_id: str,
    ) -> bool: ...

    async def add_message(
        self,
        *,
        conversation_id: str,
        principal_id: str,
        role: str,
        content: str,
        payload: dict | None = None,
    ) -> int: ...

    async def list_conversations(
        self,
        principal_id: str,
        limit: int = 25,
        offset: int = 0,
        search: str = "",
    ) -> list[dict]: ...

    async def list_messages(
        self,
        *,
        principal_id: str,
        conversation_id: str,
    ) -> list[dict]: ...

    async def persist_assistant_and_audit(
        self,
        *,
        conversation_id: str,
        principal_id: str,
        content: str,
        payload: dict,
        request_id: str,
        user_id: int | None,
        api_client_id: str | None,
        query: str,
        route: str,
        routing: dict,
        query_intelligence: dict,
        response: dict,
        answer_detail: str | None = None,
        model: str | None = None,
        latency_ms: float | None = None,
    ) -> tuple[int, int]: ...


class ThreadedConversationRepository:
    """Async adapter for the SQLite store used in development and tests."""

    def __init__(
        self,
        store_provider: Callable,
        *,
        operation_timeout_seconds: float,
    ):
        self.store_provider = store_provider
        self.operation_timeout_seconds = operation_timeout_seconds

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def _call(self, operation: str, method_name: str, **values):
        started_at = time.perf_counter()
        result = "success"
        try:
            method = getattr(self.store_provider(), method_name)
            async with asyncio.timeout(self.operation_timeout_seconds):
                return await asyncio.to_thread(method, **values)
        except TimeoutError as error:
            result = "timeout"
            raise ConversationRepositoryTimeout(
                "Database operation timed out."
            ) from error
        except ConversationRepositoryError:
            result = "error"
            raise
        except Exception as error:
            result = "error"
            raise ConversationRepositoryError(
                "Database operation failed."
            ) from error
        finally:
            observability.record_database_operation(
                operation=operation,
                duration_ms=(time.perf_counter() - started_at) * 1000,
                result=result,
            )

    async def ready(self) -> bool:
        def ping() -> bool:
            with self.store_provider().connect() as connection:
                return bool(connection.execute("SELECT 1").fetchone())

        started_at = time.perf_counter()
        result = "success"
        try:
            async with asyncio.timeout(self.operation_timeout_seconds):
                return await asyncio.to_thread(ping)
        except TimeoutError:
            result = "timeout"
            return False
        except Exception:
            result = "error"
            logger.exception("database_readiness_check_failed backend=sqlite")
            return False
        finally:
            observability.record_database_operation(
                operation="ready",
                duration_ms=(time.perf_counter() - started_at) * 1000,
                result=result,
            )

    async def list_for_principal(self, principal_id: str, limit: int = 25):
        return await self._call(
            "list_audit",
            "list_for_principal",
            principal_id=principal_id,
            limit=limit,
        )

    async def create_conversation(self, **values):
        return await self._call(
            "create_conversation",
            "create_conversation",
            **values,
        )

    async def conversation_exists(self, **values):
        return await self._call(
            "conversation_exists",
            "conversation_exists",
            **values,
        )

    async def rename_conversation(self, **values):
        return await self._call(
            "rename_conversation",
            "rename_conversation",
            **values,
        )

    async def set_conversation_pinned(self, **values):
        return await self._call(
            "pin_conversation",
            "set_conversation_pinned",
            **values,
        )

    async def delete_conversation(self, **values):
        return await self._call(
            "delete_conversation",
            "delete_conversation",
            **values,
        )

    async def add_message(self, **values):
        return await self._call(
            "add_message",
            "add_message",
            **values,
        )

    async def list_conversations(self, principal_id: str, **values):
        return await self._call(
            "list_conversations",
            "list_conversations",
            principal_id=principal_id,
            **values,
        )

    async def list_messages(self, **values):
        return await self._call(
            "list_messages",
            "list_messages",
            **values,
        )

    async def persist_assistant_and_audit(self, **values):
        return await self._call(
            "persist_research_result",
            "persist_assistant_and_audit",
            **values,
        )


class PostgresConversationRepository:
    """Pooled, non-blocking PostgreSQL persistence for production."""

    def __init__(
        self,
        database_url: str,
        *,
        min_pool_size: int,
        max_pool_size: int,
        pool_timeout_seconds: float,
        operation_timeout_seconds: float,
        connect_retries: int,
        retry_delay_seconds: float,
    ):
        if AsyncConnectionPool is None:
            raise RuntimeError(
                "psycopg-pool is required for PostgreSQL persistence."
            )
        self.database_url = normalize_database_url(database_url)
        self.min_pool_size = max(1, min_pool_size)
        self.max_pool_size = max(self.min_pool_size, max_pool_size)
        self.pool_timeout_seconds = pool_timeout_seconds
        self.operation_timeout_seconds = operation_timeout_seconds
        self.connect_retries = max(1, connect_retries)
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)
        self.pool = None

    def _new_pool(self):
        return AsyncConnectionPool(
            conninfo=self.database_url,
            min_size=self.min_pool_size,
            max_size=self.max_pool_size,
            timeout=self.pool_timeout_seconds,
            kwargs={"row_factory": tuple_row},
            check=AsyncConnectionPool.check_connection,
            open=False,
            name="finintel-conversations",
        )

    async def start(self) -> None:
        last_error = None
        for attempt in range(1, self.connect_retries + 1):
            pool = self._new_pool()
            try:
                await pool.open(
                    wait=True,
                    timeout=self.pool_timeout_seconds,
                )
                self.pool = pool
                if not await self.ready():
                    raise RuntimeError("Database readiness check failed.")
                logger.info(
                    "database_pool_started backend=postgres min=%s max=%s",
                    self.min_pool_size,
                    self.max_pool_size,
                )
                return
            except Exception as error:
                last_error = error
                await pool.close()
                self.pool = None
                logger.warning(
                    "database_pool_start_failed attempt=%s retries=%s",
                    attempt,
                    self.connect_retries,
                )
                if attempt < self.connect_retries:
                    await asyncio.sleep(self.retry_delay_seconds * attempt)

        raise RuntimeError("Unable to connect to the database.") from last_error

    async def close(self) -> None:
        if self.pool is None:
            return
        await self.pool.close(timeout=self.pool_timeout_seconds)
        self.pool = None
        logger.info("database_pool_closed backend=postgres")

    def _active_pool(self):
        if self.pool is None:
            raise RuntimeError("Database pool has not been started.")
        return self.pool

    async def _run(
        self,
        operation: str,
        callback: Callable[[Any], Coroutine[Any, Any, Any]],
    ):
        started_at = time.perf_counter()
        result = "success"
        try:
            async with asyncio.timeout(self.operation_timeout_seconds):
                async with self._active_pool().connection(
                    timeout=self.pool_timeout_seconds
                ) as connection:
                    return await callback(connection)
        except TimeoutError as error:
            result = "timeout"
            raise ConversationRepositoryTimeout(
                "Database operation timed out."
            ) from error
        except ConversationRepositoryError:
            result = "error"
            raise
        except Exception as error:
            result = "error"
            raise ConversationRepositoryError(
                "Database operation failed."
            ) from error
        finally:
            observability.record_database_operation(
                operation=operation,
                duration_ms=(time.perf_counter() - started_at) * 1000,
                result=result,
            )

    async def ready(self) -> bool:
        async def ping(connection):
            cursor = await connection.execute("SELECT 1")
            return bool(await cursor.fetchone())

        try:
            return await self._run("ready", ping)
        except Exception:
            logger.exception("database_readiness_check_failed backend=postgres")
            return False

    async def list_for_principal(
        self,
        principal_id: str,
        limit: int = 25,
    ) -> list[dict]:
        bounded_limit = max(1, min(int(limit), 100))

        async def query(connection):
            cursor = await connection.execute(
                """
                SELECT id, request_id, principal_id, user_id, api_client_id,
                       query, route, routing_json, intelligence_json,
                       response_success, response_error, response_json,
                       answer_detail, model, conversation_id, confidence_score,
                       latency_ms, created_at
                FROM chat_audit
                WHERE principal_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (principal_id, bounded_limit),
            )
            return [self._audit_record(row) for row in await cursor.fetchall()]

        return await self._run("list_audit", query)

    async def create_conversation(
        self,
        *,
        principal_id: str,
        title: str,
    ) -> str:
        conversation_id = str(uuid4())
        now = int(time.time())
        clean_title = title.strip()[:120] or "New research chat"

        async def insert(connection):
            await connection.execute(
                """
                INSERT INTO chat_conversations (
                    id, principal_id, title, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (conversation_id, principal_id, clean_title, now, now),
            )
            return conversation_id

        return await self._run("create_conversation", insert)

    async def conversation_exists(
        self,
        *,
        principal_id: str,
        conversation_id: str,
    ) -> bool:
        async def query(connection):
            cursor = await connection.execute(
                """
                SELECT 1 FROM chat_conversations
                WHERE id = %s AND principal_id = %s
                """,
                (conversation_id, principal_id),
            )
            return bool(await cursor.fetchone())

        return await self._run("conversation_exists", query)

    async def rename_conversation(
        self,
        *,
        principal_id: str,
        conversation_id: str,
        title: str,
    ) -> bool:
        clean_title = title.strip()[:120]
        if not clean_title:
            return False

        async def update(connection):
            cursor = await connection.execute(
                """
                UPDATE chat_conversations
                SET title = %s, updated_at = %s
                WHERE id = %s AND principal_id = %s
                """,
                (clean_title, int(time.time()), conversation_id, principal_id),
            )
            return cursor.rowcount > 0

        return await self._run("rename_conversation", update)

    async def set_conversation_pinned(
        self,
        *,
        principal_id: str,
        conversation_id: str,
        pinned: bool,
    ) -> bool:
        async def update(connection):
            cursor = await connection.execute(
                """
                UPDATE chat_conversations
                SET pinned = %s
                WHERE id = %s AND principal_id = %s
                """,
                (1 if pinned else 0, conversation_id, principal_id),
            )
            return cursor.rowcount > 0

        return await self._run("pin_conversation", update)

    async def delete_conversation(
        self,
        *,
        principal_id: str,
        conversation_id: str,
    ) -> bool:
        async def delete(connection):
            async with connection.transaction():
                cursor = await connection.execute(
                    """
                    SELECT 1 FROM chat_conversations
                    WHERE id = %s AND principal_id = %s
                    """,
                    (conversation_id, principal_id),
                )
                if not await cursor.fetchone():
                    return False
                await connection.execute(
                    """
                    DELETE FROM chat_messages
                    WHERE conversation_id = %s AND principal_id = %s
                    """,
                    (conversation_id, principal_id),
                )
                await connection.execute(
                    """
                    DELETE FROM chat_conversations
                    WHERE id = %s AND principal_id = %s
                    """,
                    (conversation_id, principal_id),
                )
                return True

        return await self._run("delete_conversation", delete)

    async def add_message(
        self,
        *,
        conversation_id: str,
        principal_id: str,
        role: str,
        content: str,
        payload: dict | None = None,
    ) -> int:
        async def insert(connection):
            async with connection.transaction():
                return await self._insert_message(
                    connection,
                    conversation_id=conversation_id,
                    principal_id=principal_id,
                    role=role,
                    content=content,
                    payload=payload,
                )

        return await self._run("add_message", insert)

    async def list_conversations(
        self,
        principal_id: str,
        limit: int = 25,
        offset: int = 0,
        search: str = "",
    ) -> list[dict]:
        bounded_limit = max(1, min(int(limit), 100))
        bounded_offset = max(0, int(offset))
        clean_search = search.strip().lower()[:120]

        async def query(connection):
            conditions = "principal_id = %s"
            parameters: list[Any] = [principal_id]
            if clean_search:
                conditions += " AND LOWER(title) LIKE %s"
                parameters.append(f"%{clean_search}%")
            parameters.extend([bounded_limit, bounded_offset])
            cursor = await connection.execute(
                f"""
                SELECT id, title, created_at, updated_at, pinned
                FROM chat_conversations
                WHERE {conditions}
                ORDER BY pinned DESC, updated_at DESC
                LIMIT %s OFFSET %s
                """,
                parameters,
            )
            rows = await cursor.fetchall()
            return [
                {
                    "conversation_id": row[0],
                    "title": row[1],
                    "created_at": row[2],
                    "updated_at": row[3],
                    "pinned": bool(row[4]),
                }
                for row in rows
            ]

        return await self._run("list_conversations", query)

    async def list_messages(
        self,
        *,
        principal_id: str,
        conversation_id: str,
    ) -> list[dict]:
        async def query(connection):
            cursor = await connection.execute(
                """
                SELECT id, conversation_id, principal_id, role, content,
                       payload_json, created_at
                FROM chat_messages
                WHERE principal_id = %s AND conversation_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (principal_id, conversation_id),
            )
            return [self._message_record(row) for row in await cursor.fetchall()]

        return await self._run("list_messages", query)

    async def persist_assistant_and_audit(self, **values) -> tuple[int, int]:
        async def persist(connection):
            async with connection.transaction():
                message_id = await self._insert_message(
                    connection,
                    conversation_id=values["conversation_id"],
                    principal_id=values["principal_id"],
                    role="assistant",
                    content=values["content"],
                    payload=values["payload"],
                )
                audit_id = await self._insert_audit(connection, **values)
                return message_id, audit_id

        return await self._run("persist_research_result", persist)

    @staticmethod
    async def _insert_message(
        connection,
        *,
        conversation_id: str,
        principal_id: str,
        role: str,
        content: str,
        payload: dict | None,
    ) -> int:
        now = int(time.time())
        cursor = await connection.execute(
            """
            INSERT INTO chat_messages (
                conversation_id, principal_id, role, content,
                payload_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                conversation_id,
                principal_id,
                role,
                content,
                _to_json(payload) if payload else None,
                now,
            ),
        )
        row = await cursor.fetchone()
        await connection.execute(
            """
            UPDATE chat_conversations SET updated_at = %s
            WHERE id = %s AND principal_id = %s
            """,
            (now, conversation_id, principal_id),
        )
        return int(row[0])

    @staticmethod
    async def _insert_audit(connection, **values) -> int:
        response = values["response"]
        response_payload = response.get("data", {}) or {}
        cursor = await connection.execute(
            """
            INSERT INTO chat_audit (
                request_id, principal_id, user_id, api_client_id, query,
                route, routing_json, intelligence_json, response_success,
                response_error, response_json, answer_detail, model,
                conversation_id, confidence_score, latency_ms, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
            """,
            (
                values["request_id"],
                values["principal_id"],
                values.get("user_id"),
                values.get("api_client_id"),
                values["query"],
                values["route"],
                _to_json(values["routing"]),
                _to_json(values["query_intelligence"]),
                1 if response.get("success") else 0,
                response.get("error"),
                _to_json(response),
                values.get("answer_detail"),
                values.get("model"),
                values["conversation_id"],
                response_payload.get("confidence_score"),
                values.get("latency_ms"),
                int(time.time()),
            ),
        )
        row = await cursor.fetchone()
        return int(row[0])

    @staticmethod
    def _audit_record(row) -> dict:
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
            "created_at": row[17],
        }

    @staticmethod
    def _message_record(row) -> dict:
        return {
            "id": row[0],
            "conversation_id": row[1],
            "principal_id": row[2],
            "role": row[3],
            "content": row[4],
            "payload": json.loads(row[5]) if row[5] else None,
            "created_at": row[6],
        }


def build_conversation_repository(
    *,
    database_url: str,
    database_path: str | None,
    store_provider: Callable,
    min_pool_size: int,
    max_pool_size: int,
    pool_timeout_seconds: float,
    operation_timeout_seconds: float,
    connect_retries: int,
    retry_delay_seconds: float,
) -> ConversationRepository:
    if database_path or database_backend(database_url) == "sqlite":
        return ThreadedConversationRepository(
            store_provider,
            operation_timeout_seconds=operation_timeout_seconds,
        )

    return PostgresConversationRepository(
        database_url,
        min_pool_size=min_pool_size,
        max_pool_size=max_pool_size,
        pool_timeout_seconds=pool_timeout_seconds,
        operation_timeout_seconds=operation_timeout_seconds,
        connect_retries=connect_retries,
        retry_delay_seconds=retry_delay_seconds,
    )


def _to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
