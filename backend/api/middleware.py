import logging
import time
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.observability import observability
from backend.observability.metrics import RequestTrace


logger = logging.getLogger(__name__)


def cors_headers_for_request(
    request: Request,
) -> dict[str, str]:
    origin = request.headers.get("origin")

    if (
        not origin
        or origin not in settings.FRONTEND_ALLOWED_ORIGINS
    ):
        return {}

    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


def register_middlewares(
    app: FastAPI,
    *,
    get_api_key_authenticator: Callable,
    get_clerk_authenticator: Callable,
    get_chat_rate_limiter: Callable,
):
    @app.middleware("http")
    async def chat_security_middleware(
        request: Request,
        call_next,
    ):
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path not in {
            "/chat",
            "/chat/stream",
            "/report",
            "/report/stream",
        }:
            return await call_next(request)

        provided_key = request.headers.get(
            "X-API-Key",
            "",
        )
        authorization = request.headers.get(
            "Authorization",
            "",
        )
        api_client = get_api_key_authenticator().authenticate(
            provided_key
        )
        auth_user = None

        if (
            not api_client
            and authorization.startswith("Bearer ")
        ):
            bearer_token = authorization.removeprefix(
                "Bearer "
            ).strip()
            auth_user = get_clerk_authenticator().authenticate(
                bearer_token
            )

        if not api_client and not auth_user:
            logger.warning(
                "unauthorized_chat_request client=%s",
                (
                    request.client.host
                    if request.client
                    else "unknown"
                ),
            )
            return JSONResponse(
                status_code=401,
                headers=cors_headers_for_request(request),
                content={
                    "success": False,
                    "error": "Invalid or missing credentials.",
                },
            )

        principal_id = (
            f"clerk:{auth_user.user_id}"
            if auth_user
            else f"client:{api_client.client_id}"
        )
        allowed, retry_after = get_chat_rate_limiter().allow(
            principal_id
        )

        if not allowed:
            logger.warning(
                "rate_limited_chat_request api_client=%s remote_client=%s",
                principal_id,
                (
                    request.client.host
                    if request.client
                    else "unknown"
                ),
            )
            return JSONResponse(
                status_code=429,
                headers={
                    **cors_headers_for_request(request),
                    "Retry-After": str(retry_after),
                },
                content={
                    "success": False,
                    "error": "Rate limit exceeded.",
                },
            )

        request.state.api_client = api_client
        request.state.auth_user = auth_user
        request.state.principal_id = principal_id
        return await call_next(request)

    @app.middleware("http")
    async def request_logging_middleware(
        request: Request,
        call_next,
    ):
        request_id = str(uuid4())
        started_at = time.perf_counter()
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise

        duration_ms = round(
            (time.perf_counter() - started_at) * 1000,
            2,
        )
        response.headers["X-Request-ID"] = request_id
        observability.record_request(
            RequestTrace(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                timestamp=int(time.time()),
                route=getattr(
                    request.state,
                    "route",
                    None,
                ),
                principal=getattr(
                    request.state,
                    "principal_id",
                    None,
                ),
            )
        )
        logger.info(
            "request_completed request_id=%s method=%s path=%s "
            "status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.FRONTEND_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
