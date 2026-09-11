from dataclasses import dataclass

from fastapi.security import APIKeyHeader

from backend.agents.comparison_agent import ComparisonAgent
from backend.agents.discovery_agent import DiscoveryAgent
from backend.agents.educational_agent import EducationalAgent
from backend.agents.fundamental_agent import FundamentalAgent
from backend.agents.news_agent import NewsAgent
from backend.agents.price_agent import PriceAgent
from backend.agents.report_agent import ReportAgent
from backend.agents.router_agent import RouterAgent
from backend.audit import ChatAuditStore
from backend.config import settings
from backend.intelligence.query_intelligence import QueryIntelligence
from backend.security import APIKeyAuthenticator
from backend.security import ClerkAuthenticator
from backend.utils.rate_limiter import build_rate_limiter


@dataclass(frozen=True)
class ApplicationDependencies:
    router_agent: RouterAgent
    fundamental_agent: FundamentalAgent
    comparison_agent: ComparisonAgent
    price_agent: PriceAgent
    educational_agent: EducationalAgent
    discovery_agent: DiscoveryAgent
    news_agent: NewsAgent
    report_agent: ReportAgent
    query_intelligence: QueryIntelligence
    chat_audit_store: ChatAuditStore
    chat_rate_limiter: object
    api_key_authenticator: APIKeyAuthenticator
    clerk_authenticator: ClerkAuthenticator
    api_key_header: APIKeyHeader


def build_application_dependencies() -> ApplicationDependencies:
    return ApplicationDependencies(
        router_agent=RouterAgent(),
        fundamental_agent=FundamentalAgent(),
        comparison_agent=ComparisonAgent(),
        price_agent=PriceAgent(),
        educational_agent=EducationalAgent(),
        discovery_agent=DiscoveryAgent(),
        news_agent=NewsAgent(),
        report_agent=ReportAgent(),
        query_intelligence=QueryIntelligence(),
        chat_audit_store=ChatAuditStore(),
        chat_rate_limiter=build_rate_limiter(
            limit=settings.RATE_LIMIT_PER_MINUTE,
            namespace="chat",
        ),
        api_key_authenticator=APIKeyAuthenticator(
            clients_json=settings.API_CLIENTS_JSON,
            legacy_api_key=settings.APP_API_KEY,
        ),
        clerk_authenticator=ClerkAuthenticator(),
        api_key_header=APIKeyHeader(
            name="X-API-Key",
            auto_error=False,
        ),
    )
