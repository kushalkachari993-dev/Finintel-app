import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api import conversation_context as context_tools
from backend.api.dependencies import build_application_dependencies
from backend.api.middleware import cors_headers_for_request
from backend.api.middleware import register_middlewares
from backend.api.routes.auth import create_auth_routes
from backend.api.routes.auth import user_payload
from backend.api.routes.conversations import create_conversation_router
from backend.api.routes.research import create_research_routes
from backend.api.routes.research import research_http_response
from backend.api.routes.research import research_request_metadata
from backend.api.routes.research import sse_event
from backend.api.routes.system import health
from backend.api.routes.system import health_head
from backend.api.routes.system import metrics
from backend.api.routes.system import observability_dashboard
from backend.api.routes.system import observability_snapshot
from backend.api.routes.system import root
from backend.api.routes.system import root_head
from backend.api.routes.system import router as system_router
from backend.api.schemas import ChatRequest
from backend.api.schemas import ConversationContextMessage
from backend.api.schemas import ConversationUpdateRequest
from backend.audit import ChatAuditStore
from backend.config import settings
from backend.security import APIKeyAuthenticator
from backend.security import ClerkAuthenticator
from backend.services import ResearchService
from backend.utils.logging_config import configure_logging
from backend.observability.sentry import init_sentry


configure_logging()

SENTRY_ENABLED = init_sentry()
logger = logging.getLogger(__name__)

dependencies = build_application_dependencies()

router_agent = dependencies.router_agent
fundamental_agent = dependencies.fundamental_agent
comparison_agent = dependencies.comparison_agent
price_agent = dependencies.price_agent
educational_agent = dependencies.educational_agent
discovery_agent = dependencies.discovery_agent
news_agent = dependencies.news_agent
report_agent = dependencies.report_agent
query_intelligence = dependencies.query_intelligence
chat_audit_store = dependencies.chat_audit_store
chat_rate_limiter = dependencies.chat_rate_limiter
api_key_authenticator = dependencies.api_key_authenticator
clerk_authenticator = dependencies.clerk_authenticator
api_key_header = dependencies.api_key_header

response_context_text = context_tools.response_context_text
build_generation_context = context_tools.build_generation_context
is_follow_up_query = context_tools.is_follow_up_query
join_companies = context_tools.join_companies


def stored_conversation_context(
    *,
    principal_id: str,
    conversation_id: str,
) -> list[ConversationContextMessage]:
    return context_tools.stored_conversation_context(
        principal_id=principal_id,
        conversation_id=conversation_id,
        chat_audit_store=chat_audit_store,
    )


def conversation_context_for_request(
    *,
    principal_id: str,
    conversation_id: str,
    client_context: list[ConversationContextMessage],
) -> list[ConversationContextMessage]:
    return context_tools.conversation_context_for_request(
        principal_id=principal_id,
        conversation_id=conversation_id,
        client_context=client_context,
        chat_audit_store=chat_audit_store,
    )


def context_companies(
    context: list[ConversationContextMessage],
) -> list[str]:
    return context_tools.context_companies(
        context,
        query_intelligence=query_intelligence,
    )


def standalone_follow_up_query(
    query: str,
    context: list[ConversationContextMessage],
) -> str:
    return context_tools.standalone_follow_up_query(
        query,
        context,
        query_intelligence=query_intelligence,
    )


def contextual_query(
    query: str,
    context: list[ConversationContextMessage],
) -> str:
    return context_tools.contextual_query(
        query,
        context,
        query_intelligence=query_intelligence,
    )


def build_research_service() -> ResearchService:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    settings.validate_required_settings()
    yield


app = FastAPI(
    title="FinIntel AI",
    version="2.0.0",
    lifespan=lifespan,
)

register_middlewares(
    app,
    get_api_key_authenticator=lambda: api_key_authenticator,
    get_clerk_authenticator=lambda: clerk_authenticator,
    get_chat_rate_limiter=lambda: chat_rate_limiter,
)

auth_routes = create_auth_routes(
    get_clerk_authenticator=lambda: clerk_authenticator,
    get_api_key_authenticator=lambda: api_key_authenticator,
)
get_bearer_user = auth_routes.get_bearer_user
get_authenticated_principal = (
    auth_routes.get_authenticated_principal
)

conversation_router = create_conversation_router(
    get_chat_audit_store=lambda: chat_audit_store,
    get_authenticated_principal=get_authenticated_principal,
)

RESEARCH_HEARTBEAT_SECONDS = 15

research_routes = create_research_routes(
    get_research_service=lambda: build_research_service(),
    get_heartbeat_seconds=lambda: RESEARCH_HEARTBEAT_SECONDS,
    api_key_header=api_key_header,
)
chat = research_routes.chat
chat_stream = research_routes.chat_stream
report = research_routes.report
report_stream = research_routes.report_stream
stream_research_result = research_routes.stream_research_result

app.include_router(system_router)
app.include_router(auth_routes.router)
app.include_router(conversation_router)
app.include_router(research_routes.router)
