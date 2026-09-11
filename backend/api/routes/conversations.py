from typing import Callable

from fastapi import APIRouter
from fastapi import Security
from fastapi.responses import JSONResponse

from backend.api.schemas import ConversationUpdateRequest


def create_conversation_router(
    *,
    get_chat_audit_store: Callable,
    get_authenticated_principal: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/chat/history")
    def chat_history(
        limit: int = 25,
        principal=Security(get_authenticated_principal),
    ):
        if not principal:
            return unauthorized_response()

        return {
            "success": True,
            "history": get_chat_audit_store().list_for_principal(
                principal_id=principal["principal_id"],
                limit=limit,
            ),
        }

    @router.get("/chat/conversations")
    def chat_conversations(
        limit: int = 25,
        offset: int = 0,
        search: str = "",
        principal=Security(get_authenticated_principal),
    ):
        if not principal:
            return unauthorized_response()

        page_size = max(1, min(int(limit), 50))
        bounded_offset = max(0, int(offset))
        conversations = get_chat_audit_store().list_conversations(
            principal_id=principal["principal_id"],
            limit=page_size + 1,
            offset=bounded_offset,
            search=search,
        )

        return {
            "success": True,
            "conversations": conversations[:page_size],
            "has_more": len(conversations) > page_size,
            "limit": page_size,
            "offset": bounded_offset,
            "search": search.strip()[:120],
        }

    @router.get("/chat/conversations/{conversation_id}")
    def chat_conversation_messages(
        conversation_id: str,
        principal=Security(get_authenticated_principal),
    ):
        if not principal:
            return unauthorized_response()

        store = get_chat_audit_store()
        if not store.conversation_exists(
            principal_id=principal["principal_id"],
            conversation_id=conversation_id,
        ):
            return conversation_not_found_response()

        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": store.list_messages(
                principal_id=principal["principal_id"],
                conversation_id=conversation_id,
            ),
        }

    @router.patch("/chat/conversations/{conversation_id}")
    def update_chat_conversation(
        conversation_id: str,
        update: ConversationUpdateRequest,
        principal=Security(get_authenticated_principal),
    ):
        if not principal:
            return unauthorized_response()

        principal_id = principal["principal_id"]
        store = get_chat_audit_store()
        if not store.conversation_exists(
            principal_id=principal_id,
            conversation_id=conversation_id,
        ):
            return conversation_not_found_response()

        if update.title is None and update.pinned is None:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Provide a title or pinned state.",
                },
            )

        clean_title = (
            update.title.strip()
            if update.title is not None
            else None
        )
        if update.title is not None and not clean_title:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Conversation title cannot be empty.",
                },
            )

        if clean_title is not None:
            store.rename_conversation(
                principal_id=principal_id,
                conversation_id=conversation_id,
                title=clean_title,
            )

        if update.pinned is not None:
            store.set_conversation_pinned(
                principal_id=principal_id,
                conversation_id=conversation_id,
                pinned=update.pinned,
            )

        return {
            "success": True,
            "conversation_id": conversation_id,
            "title": clean_title,
            "pinned": update.pinned,
        }

    @router.delete("/chat/conversations/{conversation_id}")
    def delete_chat_conversation(
        conversation_id: str,
        principal=Security(get_authenticated_principal),
    ):
        if not principal:
            return unauthorized_response()

        deleted = get_chat_audit_store().delete_conversation(
            principal_id=principal["principal_id"],
            conversation_id=conversation_id,
        )
        if not deleted:
            return conversation_not_found_response()

        return {
            "success": True,
            "conversation_id": conversation_id,
        }

    return router


def unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "success": False,
            "error": "Invalid or missing credentials.",
        },
    )


def conversation_not_found_response() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Conversation not found.",
        },
    )
