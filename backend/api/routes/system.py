from typing import Callable

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import Response

from backend.observability import observability


router = APIRouter()


@router.get("/")
def root():
    return {
        "message": "FinIntel AI Backend Running",
        "version": "2.0.0",
        "status": "healthy",
    }


@router.head("/")
def root_head():
    return Response(status_code=200)


@router.get("/health")
def health():
    return {
        "status": "ok",
        "agents": [
            "router_agent",
            "fundamental_agent",
            "comparison_agent",
            "price_agent",
            "educational_agent",
            "discovery_agent",
            "news_agent",
            "report_agent",
        ],
    }


@router.head("/health")
def health_head():
    return Response(status_code=200)


@router.get("/metrics")
def metrics():
    return PlainTextResponse(
        observability.prometheus_text(),
        media_type="text/plain",
    )


@router.get("/observability")
def observability_snapshot():
    return observability.snapshot()


@router.get("/observability/dashboard")
def observability_dashboard():
    return HTMLResponse(
        observability.dashboard_html()
    )


def create_system_router(
    *,
    get_conversation_repository: Callable,
) -> APIRouter:
    configured_router = APIRouter()
    configured_router.include_router(router)

    @configured_router.get("/ready")
    async def readiness():
        if await get_conversation_repository().ready():
            return {
                "status": "ok",
                "database": "ready",
            }

        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "unavailable",
            },
        )

    @configured_router.head("/ready")
    async def readiness_head():
        is_ready = await get_conversation_repository().ready()
        return Response(status_code=200 if is_ready else 503)

    return configured_router
