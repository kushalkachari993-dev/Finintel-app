import logging
import asyncio
import json
import re
import sqlite3
import time
from contextlib import asynccontextmanager
from uuid import uuid4
from typing import Literal

from fastapi import Header
from fastapi import FastAPI
from fastapi import Security
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from pydantic import Field

from backend.agents.router_agent import (
    RouterAgent
)

from backend.agents.fundamental_agent import (
    FundamentalAgent
)

from backend.agents.comparison_agent import (
    ComparisonAgent
)

from backend.agents.price_agent import (
    PriceAgent
)

from backend.agents.educational_agent import (
    EducationalAgent
)

from backend.agents.discovery_agent import (
    DiscoveryAgent
)

from backend.agents.news_agent import (
    NewsAgent
)

from backend.agents.report_agent import (
    ReportAgent
)

from backend.llm.model_selector import (
    select_groq_model
)

from backend.intelligence.query_intelligence import (
    QueryIntelligence
)

from backend.config import settings

from backend.utils.logging_config import (
    configure_logging
)

from backend.utils.rate_limiter import build_rate_limiter

from backend.utils.async_execution import (
    run_blocking
)

from backend.utils.financial_guardrails import (
    apply_financial_guardrails
)

from backend.security import APIKeyAuthenticator
from backend.security import ClerkAuthenticator
from backend.security import TokenService
from backend.security import UserStore

from backend.observability import observability
from backend.observability.metrics import RequestTrace
from backend.observability.sentry import init_sentry

from backend.audit import ChatAuditStore

configure_logging()

SENTRY_ENABLED = init_sentry()

logger = logging.getLogger(__name__)

chat_rate_limiter = build_rate_limiter(
    limit=settings.RATE_LIMIT_PER_MINUTE,
    namespace="chat"
)

api_key_authenticator = APIKeyAuthenticator(
    clients_json=settings.API_CLIENTS_JSON,
    legacy_api_key=settings.APP_API_KEY
)

user_store = UserStore()

token_service = TokenService()

clerk_authenticator = ClerkAuthenticator()

chat_audit_store = ChatAuditStore()

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False
)


@asynccontextmanager
async def lifespan(app: FastAPI):

    settings.validate_required_settings()
    user_store.apply_initial_admins(
        settings.AUTH_INITIAL_ADMIN_EMAILS
    )

    yield

# ---------------------------------------------------
# FASTAPI APP
# ---------------------------------------------------

app = FastAPI(
    title="FinIntel AI",
    version="2.0.0",
    lifespan=lifespan
)


def cors_headers_for_request(
    request: Request
) -> dict[str, str]:

    origin = request.headers.get(
        "origin"
    )

    if (
        not origin
        or origin not in settings.FRONTEND_ALLOWED_ORIGINS
    ):

        return {}

    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin"
    }


@app.middleware("http")
async def chat_security_middleware(
    request: Request,
    call_next
):

    if request.method == "OPTIONS":

        return await call_next(request)

    if request.url.path not in {
        "/chat",
        "/chat/stream",
        "/report",
        "/report/stream"
    }:

        return await call_next(request)

    provided_key = request.headers.get(
        "X-API-Key",
        ""
    )
    authorization = request.headers.get(
        "Authorization",
        ""
    )
    api_client = api_key_authenticator.authenticate(
        provided_key
    )
    auth_user = None

    if (
        not api_client
        and authorization.startswith("Bearer ")
    ):

        bearer_token = authorization.removeprefix("Bearer ").strip()
        token_payload = token_service.verify_token(
            bearer_token
        )

        if token_payload:

            auth_user = user_store.get_user_by_id(
                int(token_payload["sub"])
            )

        if not auth_user:

            auth_user = clerk_authenticator.authenticate(
                bearer_token
            )

    if (
        not api_client
        and not auth_user
    ):

        logger.warning(
            "unauthorized_chat_request client=%s",
            request.client.host
            if request.client
            else "unknown"
        )

        return JSONResponse(
            status_code=401,
            headers=cors_headers_for_request(
                request
            ),
            content={
                "success": False,
                "error": "Invalid or missing API key."
            }
        )

    principal_id = (
        f"clerk:{auth_user.user_id}"
        if getattr(
            auth_user,
            "is_clerk",
            False
        )
        else f"user:{auth_user.user_id}"
        if auth_user
        else f"client:{api_client.client_id}"
    )

    allowed, retry_after = chat_rate_limiter.allow(
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
            )
        )

        return JSONResponse(
            status_code=429,
            headers={
                **cors_headers_for_request(
                    request
                ),
                "Retry-After": str(retry_after)
            },
            content={
                "success": False,
                "error": "Rate limit exceeded."
            }
        )

    request.state.api_client = api_client
    request.state.auth_user = auth_user
    request.state.principal_id = principal_id

    return await call_next(request)


@app.middleware("http")
async def request_logging_middleware(
    request: Request,
    call_next
):

    request_id = str(uuid4())
    start_time = time.perf_counter()
    request.state.request_id = request_id

    try:

        response = await call_next(request)

    except Exception:

        logger.exception(
            "request_failed request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path
        )

        raise

    duration_ms = round(
        (
            time.perf_counter()
            - start_time
        )
        * 1000,
        2
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
                None
            ),
            principal=getattr(
                request.state,
                "principal_id",
                None
            )
        )
    )

    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms
    )

    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ---------------------------------------------------
# INITIALIZE COMPONENTS
# ---------------------------------------------------

router_agent = RouterAgent()

fundamental_agent = (
    FundamentalAgent()
)

comparison_agent = (
    ComparisonAgent()
)

price_agent = (
    PriceAgent()
)

educational_agent = (
    EducationalAgent()
)

discovery_agent = (
    DiscoveryAgent()
)

news_agent = (
    NewsAgent()
)

report_agent = (
    ReportAgent()
)

query_intelligence = (
    QueryIntelligence()
)

# ---------------------------------------------------
# REQUEST SCHEMA
# ---------------------------------------------------

class ConversationContextMessage(BaseModel):

    role: Literal["user", "assistant", "error"]
    content: str


class ChatRequest(BaseModel):

    query: str
    answer_detail: Literal["brief", "detailed"] = "brief"
    conversation_id: str | None = None
    conversation_context: list[ConversationContextMessage] = Field(
        default_factory=list
    )


class ConversationUpdateRequest(BaseModel):

    title: str | None = Field(
        default=None,
        max_length=120
    )
    pinned: bool | None = None


FOLLOW_UP_TERMS = {
    "it",
    "this",
    "that",
    "these",
    "those",
    "them",
    "they",
    "same",
    "above",
    "previous",
    "earlier"
}


def contextual_query(
    query: str,
    context: list[ConversationContextMessage]
) -> str:

    if not context:

        return query

    words = {
        word.strip(".,?!:;").lower()
        for word in query.split()
    }
    query_lower = query.lower()
    pronoun_terms = set(
        FOLLOW_UP_TERMS
    )

    if re.search(
        r"\bit\s+(stocks?|sector|companies|shares?)\b",
        query_lower
    ):

        pronoun_terms.discard(
            "it"
        )

    looks_like_follow_up = (
        len(words) <= 4
        or bool(
            words & pronoun_terms
        )
    )

    if not looks_like_follow_up:

        return query

    recent_context = "\n".join(
        f"{message.role}: {message.content}"
        for message in context[-6:]
        if message.content.strip()
    )

    if not recent_context:

        return query

    return (
        "Conversation context:\n"
        f"{recent_context}\n\n"
        "Current question:\n"
        f"{query}"
    )


class RegisterRequest(BaseModel):

    email: str
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):

    email: str
    password: str


class VerifyEmailRequest(BaseModel):

    token: str


class PasswordResetRequest(BaseModel):

    email: str


class PasswordResetConfirmRequest(BaseModel):

    token: str
    new_password: str


class AdminUserUpdateRequest(BaseModel):

    role: Literal["user", "admin"] | None = None
    active: bool | None = None
    email_verified: bool | None = None

# ---------------------------------------------------
# ROOT ROUTE
# ---------------------------------------------------

@app.get("/")
def root():

    return {

        "message":
        "FinIntel AI Backend Running",

        "version":
        "2.0.0",

        "status":
        "healthy"
    }


@app.head("/")
def root_head():

    return Response(
        status_code=200
    )

# ---------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------

@app.get("/health")
def health():

    return {

        "status":
        "ok",

        "agents": [

            "router_agent",
            "fundamental_agent",
            "comparison_agent",
            "price_agent",
            "educational_agent",
            "discovery_agent",
            "news_agent",
            "report_agent"
        ]
    }


@app.head("/health")
def health_head():

    return Response(
        status_code=200
    )


def user_payload(user):

    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "active": user.active,
        "email_verified": user.email_verified
    }


def get_bearer_user(
    authorization: str = Header(
        default=""
    )
):

    if not authorization.startswith("Bearer "):

        return None

    payload = token_service.verify_token(
        authorization.removeprefix("Bearer ").strip()
    )

    if payload:

        user = user_store.get_user_by_id(
            int(payload["sub"])
        )

        if user and user.active:

            return user

    clerk_user = clerk_authenticator.authenticate(
        authorization.removeprefix("Bearer ").strip()
    )

    if clerk_user:

        return clerk_user

    return None


def local_user_id_for_audit(user):

    if getattr(
        user,
        "is_clerk",
        False
    ):

        return None

    return user.user_id if user else None


def get_admin_user(
    user=Security(get_bearer_user)
):

    if not user or user.role != "admin":

        return None

    return user


def get_authenticated_principal(
    authorization: str = Header(
        default=""
    ),
    api_key: str = Header(
        default="",
        alias="X-API-Key"
    )
):
    api_client = api_key_authenticator.authenticate(
        api_key
    )

    if api_client:

        return {
            "principal_id": f"client:{api_client.client_id}",
            "user": None,
            "api_client": api_client
        }

    user = get_bearer_user(
        authorization
    )

    if user:

        principal_prefix = (
            "clerk"
            if getattr(
                user,
                "is_clerk",
                False
            )
            else "user"
        )

        return {
            "principal_id": f"{principal_prefix}:{user.user_id}",
            "user": user,
            "api_client": None
        }

    return None


@app.post("/auth/register")
def register(request: RegisterRequest):

    if not settings.AUTH_ALLOW_REGISTRATION:

        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Registration is disabled."
            }
        )

    if len(request.password) < 8:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Password must be at least 8 characters."
            }
        )

    try:

        role = (
            "admin"
            if user_store.normalize_email(request.email)
            in settings.AUTH_INITIAL_ADMIN_EMAILS
            else "user"
        )
        verified = role == "admin"

        user = user_store.create_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=role,
            email_verified=verified
        )

    except Exception as error:

        if (
            not isinstance(
                error,
                sqlite3.IntegrityError
            )
            and "unique" not in str(error).lower()
            and "duplicate" not in str(error).lower()
        ):

            raise

        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": "An account with this email already exists."
            }
        )

    access_token = token_service.create_token(
        user
    )
    verification_token = None

    if not user.email_verified:

        verification_token = user_store.create_email_verification_token(
            user.user_id
        )

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_payload(user),
        "email_verification_required": not user.email_verified,
        "dev_email_verification_token": verification_token
    }


@app.post("/auth/login")
def login(request: LoginRequest):

    user = user_store.authenticate(
        email=request.email,
        password=request.password
    )

    if not user:

        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Invalid email or password."
            }
        )

    return {
        "success": True,
        "access_token": token_service.create_token(
            user
        ),
        "token_type": "bearer",
        "user": user_payload(user)
    }


@app.post("/auth/verify-email")
def verify_email(request: VerifyEmailRequest):

    user = user_store.verify_email_token(
        request.token
    )

    if not user:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Invalid or expired verification token."
            }
        )

    return {
        "success": True,
        "user": user_payload(user)
    }


@app.post("/auth/password-reset/request")
def request_password_reset(request: PasswordResetRequest):

    reset_token = user_store.create_password_reset_token(
        request.email
    )

    response = {
        "success": True,
        "message": (
            "If an account exists for that email, a password reset link will be available."
        )
    }

    if reset_token:

        response[
            "dev_password_reset_token"
        ] = reset_token

    return response


@app.post("/auth/password-reset/confirm")
def confirm_password_reset(request: PasswordResetConfirmRequest):

    if len(request.new_password) < 8:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Password must be at least 8 characters."
            }
        )

    user = user_store.reset_password_with_token(
        token=request.token,
        new_password=request.new_password
    )

    if not user:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Invalid or expired reset token."
            }
        )

    return {
        "success": True,
        "user": user_payload(user)
    }


@app.get("/auth/me")
def me(user=Security(get_bearer_user)):

    if not user:

        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Invalid or missing bearer token."
            }
        )

    return {
        "success": True,
        "user": user_payload(user)
    }


@app.get("/admin/users")
def admin_list_users(
    limit: int = 100,
    admin=Security(get_admin_user)
):

    if not admin:

        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Admin access required."
            }
        )

    return {
        "success": True,
        "users": [
            user_payload(user)
            for user in user_store.list_users(
                limit=limit
            )
        ]
    }


@app.patch("/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    request: AdminUserUpdateRequest,
    admin=Security(get_admin_user)
):

    if not admin:

        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Admin access required."
            }
        )

    updated = user_store.update_user(
        user_id,
        role=request.role,
        active=request.active,
        email_verified=request.email_verified
    )

    if not updated:

        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "User not found."
            }
        )

    return {
        "success": True,
        "user": user_payload(updated)
    }


@app.get("/metrics")
def metrics():

    return PlainTextResponse(
        observability.prometheus_text(),
        media_type="text/plain"
    )


@app.get("/observability")
def observability_snapshot():

    return observability.snapshot()


@app.get("/observability/dashboard")
def observability_dashboard():

    return HTMLResponse(
        observability.dashboard_html()
    )


@app.get("/chat/history")
def chat_history(
    limit: int = 25,
    principal=Security(get_authenticated_principal)
):

    if not principal:

        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Invalid or missing credentials."
            }
        )

    return {
        "success": True,
        "history": chat_audit_store.list_for_principal(
            principal_id=principal["principal_id"],
            limit=limit
        )
    }


@app.get("/chat/conversations")
def chat_conversations(
    limit: int = 25,
    offset: int = 0,
    search: str = "",
    principal=Security(get_authenticated_principal)
):

    if not principal:

        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Invalid or missing credentials."
            }
        )

    page_size = max(
        1,
        min(
            int(limit),
            50
        )
    )
    bounded_offset = max(
        0,
        int(offset)
    )
    conversations = chat_audit_store.list_conversations(
        principal_id=principal["principal_id"],
        limit=page_size + 1,
        offset=bounded_offset,
        search=search
    )

    return {
        "success": True,
        "conversations": conversations[:page_size],
        "has_more": len(conversations) > page_size,
        "limit": page_size,
        "offset": bounded_offset,
        "search": search.strip()[:120]
    }


@app.get("/chat/conversations/{conversation_id}")
def chat_conversation_messages(
    conversation_id: str,
    principal=Security(get_authenticated_principal)
):

    if not principal:

        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Invalid or missing credentials."
            }
        )

    if not chat_audit_store.conversation_exists(
        principal_id=principal["principal_id"],
        conversation_id=conversation_id
    ):

        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "Conversation not found."
            }
        )

    return {
        "success": True,
        "conversation_id": conversation_id,
        "messages": chat_audit_store.list_messages(
            principal_id=principal["principal_id"],
            conversation_id=conversation_id
        )
    }


@app.patch("/chat/conversations/{conversation_id}")
def update_chat_conversation(
    conversation_id: str,
    update: ConversationUpdateRequest,
    principal=Security(get_authenticated_principal)
):

    if not principal:

        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Invalid or missing credentials."
            }
        )

    principal_id = principal["principal_id"]
    if not chat_audit_store.conversation_exists(
        principal_id=principal_id,
        conversation_id=conversation_id
    ):

        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "Conversation not found."
            }
        )

    if update.title is None and update.pinned is None:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Provide a title or pinned state."
            }
        )

    clean_title = update.title.strip() if update.title is not None else None
    if update.title is not None and not clean_title:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Conversation title cannot be empty."
            }
        )

    if clean_title is not None:
        chat_audit_store.rename_conversation(
            principal_id=principal_id,
            conversation_id=conversation_id,
            title=clean_title
        )

    if update.pinned is not None:
        chat_audit_store.set_conversation_pinned(
            principal_id=principal_id,
            conversation_id=conversation_id,
            pinned=update.pinned
        )

    return {
        "success": True,
        "conversation_id": conversation_id,
        "title": clean_title,
        "pinned": update.pinned
    }


@app.delete("/chat/conversations/{conversation_id}")
def delete_chat_conversation(
    conversation_id: str,
    principal=Security(get_authenticated_principal)
):

    if not principal:

        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Invalid or missing credentials."
            }
        )

    deleted = chat_audit_store.delete_conversation(
        principal_id=principal["principal_id"],
        conversation_id=conversation_id
    )
    if not deleted:

        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "Conversation not found."
            }
        )

    return {
        "success": True,
        "conversation_id": conversation_id
    }

# ---------------------------------------------------
# CHAT ROUTE
# ---------------------------------------------------

def sse_event(
    event: str,
    data: dict
) -> str:

    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
    )


@app.post("/chat")
async def chat(
    request: ChatRequest,
    http_request: Request,
    api_key: str = Security(api_key_header)
):

    # The middleware enforces this value. This dependency exists
    # so Swagger UI exposes the X-API-Key input.
    _ = api_key
    chat_started_at = time.perf_counter()

    # ---------------------------------------------------
    # USER QUERY
    # ---------------------------------------------------

    user_query = request.query.strip()
    answer_detail = request.answer_detail
    principal_id = getattr(
        http_request.state,
        "principal_id",
        None
    ) or "unknown"

    if not user_query:

        logger.warning(
            "empty_query_rejected"
        )

        return JSONResponse(
            status_code=400,
            content={

                "success": False,

                "error":
                "Query cannot be empty."
            }
        )

    conversation_id = request.conversation_id

    if conversation_id:

        if not chat_audit_store.conversation_exists(
            principal_id=principal_id,
            conversation_id=conversation_id
        ):

            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "Conversation not found."
                }
            )

    else:

        conversation_id = chat_audit_store.create_conversation(
            principal_id=principal_id,
            title=user_query
        )

    chat_audit_store.add_message(
        conversation_id=conversation_id,
        principal_id=principal_id,
        role="user",
        content=user_query
    )
    analysis_query = contextual_query(
        user_query,
        request.conversation_context
    )

    # ---------------------------------------------------
    # QUERY INTELLIGENCE
    # ---------------------------------------------------

    intelligence = await run_blocking(
        query_intelligence.extract,
        analysis_query,
        timeout_seconds=settings.EXTERNAL_CALL_TIMEOUT_SECONDS
    )

    logger.info(
        "query_intelligence query=%r intelligence=%s",
        user_query,
        intelligence
    )

    # ---------------------------------------------------
    # ROUTER
    # ---------------------------------------------------

    routing_result = await run_blocking(
        router_agent.route,
        analysis_query,
        intelligence=intelligence,
        timeout_seconds=settings.EXTERNAL_CALL_TIMEOUT_SECONDS
    )

    route = routing_result.get(
        "route",
        "FUNDAMENTAL"
    )
    selected_model = select_groq_model(
        route,
        answer_detail
    )
    http_request.state.route = route

    logger.info(
        "route_selected query=%r route=%s model=%s routing=%s",
        user_query,
        route,
        selected_model,
        routing_result
    )

    # ---------------------------------------------------
    # ROUTE EXECUTION
    # ---------------------------------------------------

    try:

        # -----------------------------------
        # FUNDAMENTAL
        # -----------------------------------

        if route == "FUNDAMENTAL":

            response = await run_blocking(
                fundamental_agent.analyze,
                query=analysis_query,
                intelligence=intelligence,
                model=selected_model,
                answer_detail=answer_detail,
                timeout_seconds=settings.CHAT_EXECUTION_TIMEOUT_SECONDS
            )

        # -----------------------------------
        # PRICE QUERY
        # -----------------------------------

        elif route == "PRICE_QUERY":

            response = await run_blocking(
                price_agent.get_price,
                analysis_query,
                answer_detail=answer_detail,
                timeout_seconds=settings.CHAT_EXECUTION_TIMEOUT_SECONDS
            )

        # -----------------------------------
        # COMPARISON
        # -----------------------------------

        elif route == "COMPARISON":

            response = await run_blocking(
                comparison_agent.compare,
                analysis_query,
                intelligence=intelligence,
                model=selected_model,
                answer_detail=answer_detail,
                timeout_seconds=settings.CHAT_EXECUTION_TIMEOUT_SECONDS
            )

        # -----------------------------------
        # EDUCATIONAL
        # -----------------------------------

        elif route == "EDUCATIONAL":

            response = await run_blocking(
                educational_agent.explain,
                analysis_query,
                model=selected_model,
                answer_detail=answer_detail,
                timeout_seconds=settings.CHAT_EXECUTION_TIMEOUT_SECONDS
            )

        # -----------------------------------
        # NEWS
        # -----------------------------------

        elif route == "NEWS":

            response = await run_blocking(
                news_agent.analyze,
                analysis_query,
                intelligence=intelligence,
                model=selected_model,
                answer_detail=answer_detail,
                timeout_seconds=settings.CHAT_EXECUTION_TIMEOUT_SECONDS
            )

        # -----------------------------------
        # DISCOVERY
        # -----------------------------------

        elif route == "DISCOVERY":

            response = await run_blocking(
                discovery_agent.discover,
                analysis_query,
                intelligence=intelligence,
                model=selected_model,
                answer_detail=answer_detail,
                timeout_seconds=settings.CHAT_EXECUTION_TIMEOUT_SECONDS
            )

        # -----------------------------------
        # SAFE FALLBACK
        # -----------------------------------

        else:

            response = await run_blocking(
                fundamental_agent.analyze,
                analysis_query,
                model=selected_model,
                answer_detail=answer_detail,
                timeout_seconds=settings.CHAT_EXECUTION_TIMEOUT_SECONDS
            )

            route = "FUNDAMENTAL"

            routing_result = {

                "route":
                "FUNDAMENTAL",

                "confidence":
                0.30,

                "reasoning":
                "Fallback route triggered."
            }

        # ---------------------------------------------------
        # FINAL RESPONSE
        # ---------------------------------------------------

        response = apply_financial_guardrails(
            response,
            route
        )

        final_response = {

            "success": True,

            "query":
            user_query,

            "conversation_id":
            conversation_id,

            "answer_detail":
            answer_detail,

            "route":
            route,

            "routing":
            routing_result,

            "query_intelligence":
            intelligence,

            "model":
            selected_model,

            "response":
            response
        }

        chat_audit_store.add_message(
            conversation_id=conversation_id,
            principal_id=principal_id,
            role="assistant",
            content=(
                response.get(
                    "error"
                )
                or "Analysis completed."
            ),
            payload=final_response
        )

        chat_audit_store.record_chat(
            request_id=getattr(
                http_request.state,
                "request_id",
                ""
            ),
            principal_id=getattr(
                http_request.state,
                "principal_id",
                None
            ),
            user_id=(
                local_user_id_for_audit(
                    getattr(
                        http_request.state,
                        "auth_user",
                        None
                    )
                )
            ),
            api_client_id=(
                http_request.state.api_client.client_id
                if getattr(
                    http_request.state,
                    "api_client",
                    None
                )
                else None
            ),
            query=user_query,
            route=route,
            routing=routing_result,
            query_intelligence=intelligence,
            response=response,
            answer_detail=answer_detail,
            model=selected_model,
            conversation_id=conversation_id,
            latency_ms=round(
                (
                    time.perf_counter()
                    - chat_started_at
                )
                * 1000,
                2
            )
        )

        return final_response

    # ---------------------------------------------------
    # GLOBAL ERROR HANDLER
    # ---------------------------------------------------

    except Exception as e:

        if isinstance(
            e,
            TimeoutError
        ):

            logger.warning(
                "chat_timed_out query=%r route=%s",
                user_query,
                route
            )

            error_response = {
                "success": False,
                "error": "Request timed out while waiting for external providers."
            }

            chat_audit_store.add_message(
                conversation_id=conversation_id,
                principal_id=principal_id,
                role="assistant",
                content=error_response["error"],
                payload={
                    "success": False,
                    "query": user_query,
                    "conversation_id": conversation_id,
                    "answer_detail": answer_detail,
                    "route": route,
                    "routing": routing_result,
                    "query_intelligence": intelligence,
                    "model": selected_model,
                    "response": error_response
                }
            )

            chat_audit_store.record_chat(
                request_id=getattr(
                    http_request.state,
                    "request_id",
                    ""
                ),
                principal_id=getattr(
                    http_request.state,
                    "principal_id",
                    None
                ),
                user_id=(
                    local_user_id_for_audit(
                        getattr(
                            http_request.state,
                            "auth_user",
                            None
                        )
                    )
                ),
                api_client_id=(
                    http_request.state.api_client.client_id
                    if getattr(
                        http_request.state,
                        "api_client",
                        None
                    )
                    else None
                ),
                query=user_query,
                route=route,
                routing=routing_result,
                query_intelligence=intelligence,
                response=error_response,
                answer_detail=answer_detail,
                model=selected_model,
                conversation_id=conversation_id,
                latency_ms=round(
                    (
                        time.perf_counter()
                        - chat_started_at
                    )
                    * 1000,
                    2
                )
            )

            return JSONResponse(
                status_code=504,
                content={

                    "success": False,

                    "query":
                    user_query,

                    "answer_detail":
                    answer_detail,

                    "route":
                    route,

                    "routing":
                    routing_result,

                    "query_intelligence":
                    intelligence,

                    "error":
                    error_response["error"]
                }
            )

        logger.exception(
            "chat_failed query=%r route=%s",
            user_query,
            route
        )

        error_response = {
            "success": False,
            "error": str(e)
        }

        chat_audit_store.add_message(
            conversation_id=conversation_id,
            principal_id=principal_id,
            role="assistant",
            content=error_response["error"],
            payload={
                "success": False,
                "query": user_query,
                "conversation_id": conversation_id,
                "answer_detail": answer_detail,
                "route": route,
                "routing": routing_result,
                "query_intelligence": intelligence,
                "model": selected_model,
                "response": error_response
            }
        )

        chat_audit_store.record_chat(
            request_id=getattr(
                http_request.state,
                "request_id",
                ""
            ),
            principal_id=getattr(
                http_request.state,
                "principal_id",
                None
            ),
            user_id=(
                local_user_id_for_audit(
                    getattr(
                        http_request.state,
                        "auth_user",
                        None
                    )
                )
            ),
            api_client_id=(
                http_request.state.api_client.client_id
                if getattr(
                    http_request.state,
                    "api_client",
                    None
                )
                else None
            ),
            query=user_query,
            route=route,
            routing=routing_result,
            query_intelligence=intelligence,
            response=error_response,
            answer_detail=answer_detail,
            model=selected_model,
            conversation_id=conversation_id,
            latency_ms=round(
                (
                    time.perf_counter()
                    - chat_started_at
                )
                * 1000,
                2
            )
        )

        return JSONResponse(
            status_code=500,
            content={

                "success": False,

                "query":
                user_query,

                "answer_detail":
                answer_detail,

                "route":
                route,

                "routing":
                routing_result,

                "query_intelligence":
                intelligence,

                "error":
                error_response["error"]
            }
        )


@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request
):

    async def event_generator():

        progress_steps = [
            "Understanding your question...",
            "Checking conversation context...",
            "Routing to the right research workflow...",
            "Fetching market data and sources...",
            "Generating a grounded answer...",
            "Finalizing response..."
        ]

        for index, step in enumerate(
            progress_steps,
            start=1
        ):

            yield sse_event(
                "progress",
                {
                    "step": step,
                    "index": index,
                    "total": len(progress_steps)
                }
            )
            await asyncio.sleep(
                0.05
            )

        result = await chat(
            request=request,
            http_request=http_request,
            api_key=""
        )

        if isinstance(
            result,
            JSONResponse
        ):

            payload = json.loads(
                result.body.decode(
                    "utf-8"
                )
            )
            yield sse_event(
                "error",
                payload
            )
            return

        yield sse_event(
            "final",
            result
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/report")
async def report(
    request: ChatRequest,
    http_request: Request,
    api_key: str = Security(api_key_header)
):

    _ = api_key
    report_started_at = time.perf_counter()

    user_query = request.query.strip()
    answer_detail = "detailed"
    route = "REPORT"
    principal_id = getattr(
        http_request.state,
        "principal_id",
        None
    ) or "unknown"

    if not user_query:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Query cannot be empty."
            }
        )

    conversation_id = request.conversation_id

    if conversation_id:

        if not chat_audit_store.conversation_exists(
            principal_id=principal_id,
            conversation_id=conversation_id
        ):

            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "Conversation not found."
                }
            )

    else:

        conversation_id = chat_audit_store.create_conversation(
            principal_id=principal_id,
            title=user_query
        )

    chat_audit_store.add_message(
        conversation_id=conversation_id,
        principal_id=principal_id,
        role="user",
        content=user_query
    )
    analysis_query = contextual_query(
        user_query,
        request.conversation_context
    )

    intelligence = await run_blocking(
        query_intelligence.extract,
        analysis_query,
        timeout_seconds=settings.EXTERNAL_CALL_TIMEOUT_SECONDS
    )
    selected_model = select_groq_model(
        route,
        answer_detail
    )
    http_request.state.route = route

    routing_result = {
        "route": route,
        "confidence": 1.0,
        "reasoning": "Report mode selected by user."
    }

    try:

        response = await run_blocking(
            report_agent.generate,
            query=analysis_query,
            intelligence=intelligence,
            model=selected_model,
            timeout_seconds=settings.CHAT_EXECUTION_TIMEOUT_SECONDS
        )
        response = apply_financial_guardrails(
            response,
            route
        )

        final_response = {
            "success": True,
            "query": user_query,
            "conversation_id": conversation_id,
            "answer_detail": answer_detail,
            "route": route,
            "routing": routing_result,
            "query_intelligence": intelligence,
            "model": selected_model,
            "response": response
        }

        chat_audit_store.add_message(
            conversation_id=conversation_id,
            principal_id=principal_id,
            role="assistant",
            content=(
                response.get(
                    "error"
                )
                or "Report generated."
            ),
            payload=final_response
        )
        chat_audit_store.record_chat(
            request_id=getattr(
                http_request.state,
                "request_id",
                ""
            ),
            principal_id=getattr(
                http_request.state,
                "principal_id",
                None
            ),
            user_id=(
                local_user_id_for_audit(
                    getattr(
                        http_request.state,
                        "auth_user",
                        None
                    )
                )
            ),
            api_client_id=(
                http_request.state.api_client.client_id
                if getattr(
                    http_request.state,
                    "api_client",
                    None
                )
                else None
            ),
            query=user_query,
            route=route,
            routing=routing_result,
            query_intelligence=intelligence,
            response=response,
            answer_detail=answer_detail,
            model=selected_model,
            conversation_id=conversation_id,
            latency_ms=round(
                (
                    time.perf_counter()
                    - report_started_at
                )
                * 1000,
                2
            )
        )

        return final_response

    except Exception as e:

        logger.exception(
            "report_failed query=%r",
            user_query
        )

        error_response = {
            "success": False,
            "error": str(e)
        }
        chat_audit_store.add_message(
            conversation_id=conversation_id,
            principal_id=principal_id,
            role="assistant",
            content=error_response["error"],
            payload={
                "success": False,
                "query": user_query,
                "conversation_id": conversation_id,
                "answer_detail": answer_detail,
                "route": route,
                "routing": routing_result,
                "query_intelligence": intelligence,
                "model": selected_model,
                "response": error_response
            }
        )
        chat_audit_store.record_chat(
            request_id=getattr(
                http_request.state,
                "request_id",
                ""
            ),
            principal_id=getattr(
                http_request.state,
                "principal_id",
                None
            ),
            user_id=(
                local_user_id_for_audit(
                    getattr(
                        http_request.state,
                        "auth_user",
                        None
                    )
                )
            ),
            api_client_id=(
                http_request.state.api_client.client_id
                if getattr(
                    http_request.state,
                    "api_client",
                    None
                )
                else None
            ),
            query=user_query,
            route=route,
            routing=routing_result,
            query_intelligence=intelligence,
            response=error_response,
            answer_detail=answer_detail,
            model=selected_model,
            conversation_id=conversation_id,
            latency_ms=round(
                (
                    time.perf_counter()
                    - report_started_at
                )
                * 1000,
                2
            )
        )

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "query": user_query,
                "answer_detail": answer_detail,
                "route": route,
                "routing": routing_result,
                "query_intelligence": intelligence,
                "error": error_response["error"]
            }
        )


@app.post("/report/stream")
async def report_stream(
    request: ChatRequest,
    http_request: Request
):

    async def event_generator():

        progress_steps = [
            "Understanding the report brief...",
            "Checking conversation context...",
            "Resolving companies and themes...",
            "Retrieving financial data and sources...",
            "Assembling analyst sections...",
            "Finalizing structured report..."
        ]

        for index, step in enumerate(
            progress_steps,
            start=1
        ):

            yield sse_event(
                "progress",
                {
                    "step": step,
                    "index": index,
                    "total": len(progress_steps)
                }
            )
            await asyncio.sleep(
                0.05
            )

        result = await report(
            request=request,
            http_request=http_request,
            api_key=""
        )

        if isinstance(
            result,
            JSONResponse
        ):

            payload = json.loads(
                result.body.decode(
                    "utf-8"
                )
            )
            yield sse_event(
                "error",
                payload
            )
            return

        yield sse_event(
            "final",
            result
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
