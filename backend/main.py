import logging
import asyncio
import json
import re
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

from backend.intelligence.query_intelligence import (
    QueryIntelligence
)

from backend.config import settings

from backend.utils.logging_config import (
    configure_logging
)

from backend.utils.rate_limiter import build_rate_limiter

from backend.security import APIKeyAuthenticator
from backend.security import ClerkAuthenticator

from backend.services import ResearchService

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

clerk_authenticator = ClerkAuthenticator()

chat_audit_store = ChatAuditStore()

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False
)


@asynccontextmanager
async def lifespan(app: FastAPI):

    settings.validate_required_settings()

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
                "error": "Invalid or missing credentials."
            }
        )

    principal_id = (
        f"clerk:{auth_user.user_id}"
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
    "its",
    "itself",
    "this",
    "that",
    "these",
    "those",
    "them",
    "they",
    "their",
    "theirs",
    "both",
    "former",
    "latter",
    "same",
    "above",
    "previous",
    "earlier"
}

FOLLOW_UP_PATTERNS = (
    r"^\s*(?:and|also|then)\b",
    r"\b(?:what|how)\s+about\b",
    r"\bwhich\s+(?:one|company|stock)\b",
    r"\b(?:tell|show|give)\s+me\s+more\b",
    r"\b(?:explain|tell me)\s+(?:why|how)\b",
    r"\b(?:you|your)\s+(?:said|mentioned|stated|concluded|answer|analysis)\b",
    r"\bbased\s+on\s+(?:that|this|your|the previous)\b",
    r"\bexplain\s+(?:that|this|it)\b",
    r"\b(?:more|further)\s+(?:detail|details|information|analysis)\b",
    r"\b(?:instead|alternatively)\b"
)

TERSE_FOLLOW_UP_QUERIES = {
    "why",
    "why not",
    "how so",
    "explain",
    "elaborate",
    "continue",
    "go on",
    "more",
    "more details",
    "source",
    "sources",
    "risks",
    "what risks",
    "valuation",
    "outlook",
    "debt",
    "margins",
    "growth",
    "dividends"
}

CONVERSATION_CONTEXT_MESSAGE_LIMIT = 8
CONVERSATION_CONTEXT_CONTENT_LIMIT = 2000
GENERATION_CONTEXT_MESSAGE_LIMIT = 6
GENERATION_CONTEXT_TOTAL_LIMIT = 6000


def response_context_text(
    response: dict | None
) -> str:

    if not isinstance(response, dict):

        return ""

    value = response.get(
        "data"
    )

    if value is None:

        value = response.get(
            "error"
        )

    if value is None:

        return ""

    if isinstance(value, str):

        text = value

    else:

        text = json.dumps(
            value,
            ensure_ascii=False,
            default=str,
            separators=(",", ":")
        )

    return text.strip()[
        :CONVERSATION_CONTEXT_CONTENT_LIMIT
    ]


def stored_conversation_context(
    *,
    principal_id: str,
    conversation_id: str
) -> list[ConversationContextMessage]:

    messages = chat_audit_store.list_messages(
        principal_id=principal_id,
        conversation_id=conversation_id
    )
    context: list[ConversationContextMessage] = []

    for message in messages[
        -CONVERSATION_CONTEXT_MESSAGE_LIMIT:
    ]:
        role = message.get(
            "role"
        )
        content = str(
            message.get(
                "content"
            ) or ""
        ).strip()

        if role == "assistant":
            payload = message.get(
                "payload"
            )
            response = (
                payload.get(
                    "response"
                )
                if isinstance(payload, dict)
                else None
            )
            content = (
                response_context_text(
                    response
                )
                or content
            )

        if role not in {
            "user",
            "assistant",
            "error"
        } or not content:

            continue

        context.append(
            ConversationContextMessage(
                role=role,
                content=content[
                    :CONVERSATION_CONTEXT_CONTENT_LIMIT
                ]
            )
        )

    return context


def conversation_context_for_request(
    *,
    principal_id: str,
    conversation_id: str,
    client_context: list[ConversationContextMessage]
) -> list[ConversationContextMessage]:

    stored_context = stored_conversation_context(
        principal_id=principal_id,
        conversation_id=conversation_id
    )

    if stored_context:

        return stored_context

    return client_context[
        -CONVERSATION_CONTEXT_MESSAGE_LIMIT:
    ]


def build_generation_context(
    context: list[ConversationContextMessage]
) -> str:

    blocks: list[str] = []
    remaining = GENERATION_CONTEXT_TOTAL_LIMIT

    for message in reversed(
        context[-GENERATION_CONTEXT_MESSAGE_LIMIT:]
    ):
        if message.role not in {
            "user",
            "assistant"
        }:

            continue

        content = message.content.strip()

        if not content:

            continue

        label = (
            "USER"
            if message.role == "user"
            else "ASSISTANT"
        )
        prefix = f"{label}: "
        available = remaining - len(
            prefix
        ) - 1

        if available <= 0:

            break

        block = prefix + content[
            :available
        ]
        blocks.append(
            block
        )
        remaining -= len(
            block
        ) + 1

    return "\n".join(
        reversed(
            blocks
        )
    )


def is_follow_up_query(
    query: str
) -> bool:

    words = {
        word.strip(".,?!:;").lower()
        for word in query.split()
    }
    query_lower = query.lower()
    normalized_query = " ".join(
        word.strip(".,?!:;").lower()
        for word in query.split()
    )
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

    return (
        bool(
            words & pronoun_terms
        )
        or normalized_query in TERSE_FOLLOW_UP_QUERIES
        or any(
            re.search(
                pattern,
                query_lower
            )
            for pattern in FOLLOW_UP_PATTERNS
        )
    )


def context_companies(
    context: list[ConversationContextMessage]
) -> list[str]:

    collected: list[str] = []

    for message in reversed(
        context
    ):
        if message.role != "user":

            continue

        message_companies = (
            query_intelligence
            .symbol_registry
            .extract_company_names(
                message.content
            )
        )

        if message_companies:

            collected = list(
                dict.fromkeys(
                    message_companies
                    + collected
                )
            )

        if not is_follow_up_query(
            message.content
        ):

            break

    return collected


def join_companies(
    companies: list[str]
) -> str:

    if len(companies) == 1:

        return companies[0]

    if len(companies) == 2:

        return f"{companies[0]} and {companies[1]}"

    return (
        ", ".join(
            companies[:-1]
        )
        + f", and {companies[-1]}"
    )


def standalone_follow_up_query(
    query: str,
    context: list[ConversationContextMessage]
) -> str:

    companies = context_companies(
        context
    )
    current_companies = (
        query_intelligence
        .symbol_registry
        .extract_company_names(
            query
        )
    )
    normalized_query = " ".join(
        word.strip(".,?!:;").lower()
        for word in query.split()
    )

    if companies and re.search(
        r"\b(?:compare|vs|versus)\b",
        query,
        flags=re.IGNORECASE
    ):
        comparison_companies = list(
            dict.fromkeys(
                companies
                + current_companies
            )
        )

        if len(comparison_companies) >= 2:

            return (
                "Compare "
                + join_companies(
                    comparison_companies
                )
            )

    if companies and re.match(
        r"^\s*(?:and|what about|how about)\b",
        query,
        flags=re.IGNORECASE
    ) and current_companies:
        comparison_companies = list(
            dict.fromkeys(
                companies
                + current_companies
            )
        )

        return (
            "Compare "
            + join_companies(
                comparison_companies
            )
        )

    if companies:
        subject = join_companies(
            companies
        )
        primary = companies[0]
        plural_possessive = (
            f"{subject}'"
            if subject.endswith("s")
            else f"{subject}'s"
        )
        replacements = (
            (
                r"\bwhich\s+(?:one|company|stock)\b",
                f"which of {subject}"
            ),
            (r"\bformer\b", companies[0]),
            (
                r"\blatter\b",
                companies[1]
                if len(companies) > 1
                else primary
            ),
            (r"\b(?:both|they|them|these|those)\b", subject),
            (r"\btheir\b", plural_possessive),
            (r"\bits\b", f"{primary}'s"),
            (r"\bitself\b", primary),
            (
                r"\b(?:it|this company|that company|the company)\b",
                primary
            )
        )
        resolved_query = query

        for pattern, replacement in replacements:
            resolved_query = re.sub(
                pattern,
                replacement,
                resolved_query,
                flags=re.IGNORECASE
            )

        if resolved_query != query:

            return resolved_query

        topic_match = re.match(
            r"^\s*(?:and|what about|how about)\s+(.+?)[?.!]*$",
            query,
            flags=re.IGNORECASE
        )

        if topic_match:

            return (
                f"Analyze {topic_match.group(1).strip()} "
                f"for {subject}"
            )

        if normalized_query in TERSE_FOLLOW_UP_QUERIES:

            if normalized_query in {
                "why",
                "why not",
                "how so"
            }:

                return f"Explain the reasoning for {subject}"

            if normalized_query in {
                "more",
                "more details",
                "explain",
                "elaborate",
                "continue",
                "go on"
            }:

                return f"Provide more details about {subject}"

            if normalized_query in {
                "source",
                "sources"
            }:

                return f"Show the sources for {subject}"

            return f"Analyze {normalized_query} for {subject}"

        return f"{query.rstrip()} regarding {subject}"

    previous_user_query = next(
        (
            message.content.strip()
            for message in reversed(
                context
            )
            if message.role == "user"
            and message.content.strip()
        ),
        ""
    )

    if previous_user_query:

        return (
            f"{query.rstrip()} regarding the previous topic: "
            f"{previous_user_query.lower()}"
        )

    return query


def contextual_query(
    query: str,
    context: list[ConversationContextMessage]
) -> str:

    if not context:

        return query

    if not is_follow_up_query(
        query
    ):

        return query

    return standalone_follow_up_query(
        query,
        context[-6:]
    )


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

    return clerk_authenticator.authenticate(
        authorization.removeprefix("Bearer ").strip()
    )


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
        return {
            "principal_id": f"clerk:{user.user_id}",
            "user": user,
            "api_client": None
        }

    return None


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
# RESEARCH ROUTES
# ---------------------------------------------------

def build_research_service() -> ResearchService:
    """Build from current dependencies so test/runtime overrides remain visible."""

    return ResearchService(
        router_agent=router_agent,
        fundamental_agent=fundamental_agent,
        comparison_agent=comparison_agent,
        price_agent=price_agent,
        educational_agent=educational_agent,
        discovery_agent=discovery_agent,
        news_agent=news_agent,
        report_agent=report_agent,
        query_intelligence=query_intelligence,
        chat_audit_store=chat_audit_store,
        conversation_context_for_request=conversation_context_for_request,
        contextual_query=contextual_query,
        build_generation_context=build_generation_context,
        is_follow_up_query=is_follow_up_query,
        response_context_text=response_context_text,
    )


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


def research_http_response(
    outcome,
):
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


RESEARCH_HEARTBEAT_SECONDS = 15


async def stream_research_result(
    *,
    request: ChatRequest,
    http_request: Request,
    mode: Literal["chat", "report"],
):
    service = build_research_service()
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
                    timeout=RESEARCH_HEARTBEAT_SECONDS,
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


@app.post("/chat")
async def chat(
    request: ChatRequest,
    http_request: Request,
    api_key: str = Security(api_key_header),
):
    # The middleware enforces this value. This dependency exists
    # so Swagger UI exposes the X-API-Key input.
    _ = api_key
    outcome = await build_research_service().execute_chat(
        query=request.query,
        answer_detail=request.answer_detail,
        conversation_id=request.conversation_id,
        client_context=request.conversation_context,
        **research_request_metadata(http_request),
    )
    return research_http_response(outcome)


@app.post("/chat/stream")
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


@app.post("/report")
async def report(
    request: ChatRequest,
    http_request: Request,
    api_key: str = Security(api_key_header),
):
    _ = api_key
    outcome = await build_research_service().execute_report(
        query=request.query,
        conversation_id=request.conversation_id,
        client_context=request.conversation_context,
        **research_request_metadata(http_request),
    )
    return research_http_response(outcome)


@app.post("/report/stream")
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
