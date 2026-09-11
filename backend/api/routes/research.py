import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Callable
from typing import Literal

from fastapi import APIRouter
from fastapi import Request
from fastapi import Security
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse

from backend.api.schemas import ChatRequest


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResearchRoutes:
    router: APIRouter
    chat: Callable
    chat_stream: Callable
    report: Callable
    report_stream: Callable
    stream_research_result: Callable


def research_request_metadata(
    http_request: Request,
) -> dict:
    state = http_request.state
    api_client = getattr(
        state,
        "api_client",
        None,
    )

    return {
        "principal_id": (
            getattr(
                state,
                "principal_id",
                None,
            )
            or "unknown"
        ),
        "request_id": getattr(
            state,
            "request_id",
            "",
        ),
        "api_client_id": (
            api_client.client_id
            if api_client
            else None
        ),
        "on_route_selected": (
            lambda route: setattr(
                state,
                "route",
                route,
            )
        ),
    }


def research_http_response(outcome):
    if outcome.status_code == 200:
        return outcome.payload

    return JSONResponse(
        status_code=outcome.status_code,
        content=outcome.payload,
    )


def sse_event(
    event: str,
    data: dict,
) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
    )


def create_research_routes(
    *,
    get_research_service: Callable,
    get_heartbeat_seconds: Callable[[], float],
    api_key_header,
) -> ResearchRoutes:
    router = APIRouter()

    async def stream_research_result(
        *,
        request: ChatRequest,
        http_request: Request,
        mode: Literal["chat", "report"],
    ):
        service = get_research_service()
        progress_queue = asyncio.Queue()

        def on_progress(
            stage: str,
            payload: dict,
        ):
            progress_queue.put_nowait(
                (
                    stage,
                    payload,
                )
            )

        async def execute_research():
            metadata = research_request_metadata(
                http_request
            )

            if mode == "report":
                return await service.execute_report(
                    query=request.query,
                    conversation_id=request.conversation_id,
                    client_context=request.conversation_context,
                    on_progress=on_progress,
                    **metadata,
                )

            return await service.execute_chat(
                query=request.query,
                answer_detail=request.answer_detail,
                conversation_id=request.conversation_id,
                client_context=request.conversation_context,
                on_progress=on_progress,
                **metadata,
            )

        research_task = asyncio.create_task(
            execute_research()
        )
        progress_index = 0

        try:
            while not (
                research_task.done()
                and progress_queue.empty()
            ):
                try:
                    stage, progress = await asyncio.wait_for(
                        progress_queue.get(),
                        timeout=get_heartbeat_seconds(),
                    )
                except asyncio.TimeoutError:
                    if research_task.done():
                        continue

                    yield sse_event(
                        "heartbeat",
                        {
                            "timestamp": int(time.time()),
                        },
                    )
                    continue

                progress_index += 1
                progress_payload = dict(progress)
                step = progress_payload.pop(
                    "message",
                    stage,
                )
                yield sse_event(
                    "progress",
                    {
                        "stage": stage,
                        "step": step,
                        "index": progress_index,
                        "total": service.SUCCESS_PROGRESS_TOTAL,
                        **progress_payload,
                    },
                )

            outcome = await research_task
        except Exception:
            logger.exception(
                "research_stream_failed mode=%s",
                mode,
            )
            yield sse_event(
                "error",
                {
                    "success": False,
                    "error": "Research request failed unexpectedly.",
                },
            )
            return
        finally:
            if not research_task.done():
                research_task.cancel()
                try:
                    await research_task
                except asyncio.CancelledError:
                    pass

        terminal_event = (
            "final"
            if outcome.status_code == 200
            else "error"
        )
        yield sse_event(
            terminal_event,
            outcome.payload,
        )

    @router.post("/chat")
    async def chat(
        request: ChatRequest,
        http_request: Request,
        api_key: str = Security(api_key_header),
    ):
        _ = api_key
        outcome = await get_research_service().execute_chat(
            query=request.query,
            answer_detail=request.answer_detail,
            conversation_id=request.conversation_id,
            client_context=request.conversation_context,
            **research_request_metadata(http_request),
        )
        return research_http_response(outcome)

    @router.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        http_request: Request,
    ):
        return StreamingResponse(
            stream_research_result(
                request=request,
                http_request=http_request,
                mode="chat",
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/report")
    async def report(
        request: ChatRequest,
        http_request: Request,
        api_key: str = Security(api_key_header),
    ):
        _ = api_key
        outcome = await get_research_service().execute_report(
            query=request.query,
            conversation_id=request.conversation_id,
            client_context=request.conversation_context,
            **research_request_metadata(http_request),
        )
        return research_http_response(outcome)

    @router.post("/report/stream")
    async def report_stream(
        request: ChatRequest,
        http_request: Request,
    ):
        return StreamingResponse(
            stream_research_result(
                request=request,
                http_request=http_request,
                mode="report",
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return ResearchRoutes(
        router=router,
        chat=chat,
        chat_stream=chat_stream,
        report=report,
        report_stream=report_stream,
        stream_research_result=stream_research_result,
    )
