from backend.tools.news_tool import (
    NewsTool
)

from backend.tools.ticker_resolver import (
    TickerResolver
)

from backend.llm.groq_provider import (
    GroqProvider
)

from backend.utils.json_parser import (
    JSONParser
)

from backend.schemas.news_schema import (
    NewsResponse
)

from backend.utils.confidence_engine import (
    ConfidenceEngine
)

from backend.tools.financial_normalizer import (
    FinancialNormalizer
)

from backend.config.settings import (
    USD_TO_INR_RATE
)
from backend.agents.detail_guidance import (
    answer_detail_guidance,
    answer_detail_tokens,
    conversation_context_guidance
)
from backend.utils.provider_errors import (
    is_provider_error_text,
    safe_provider_error
)


class NewsAgent:

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        self.news_tool = (
            NewsTool()
        )

        self.ticker_resolver = (
            TickerResolver()
        )

        self.groq = (
            GroqProvider()
        )

        self.confidence_engine = (
            ConfidenceEngine()
        )

    @staticmethod
    def clean_news_text(
        text: str
    ) -> str:
        return " ".join(
            (text or "").split()
        )[:320]

    @staticmethod
    def build_fallback_response(
        *,
        company_name: str,
        ticker: str,
        news_articles: list,
        sources: list
    ) -> dict:
        key_events = []
        risk_factors = []

        for article in news_articles[:4]:
            title = NewsAgent.clean_news_text(
                article.get(
                    "title",
                    ""
                )
            )
            content = NewsAgent.clean_news_text(
                article.get(
                    "content",
                    ""
                )
            )

            if title:
                key_events.append(
                    title
                )
            elif content:
                key_events.append(
                    content
                )

        if not key_events:
            key_events = [
                "Relevant news sources were retrieved, but the model response could not be parsed into structured analysis."
            ]

        risk_factors = [
            "News context may be incomplete or change quickly during market hours.",
            "Validate any price-sensitive development with exchange filings and company disclosures.",
            "Do not treat news sentiment alone as an investment decision."
        ]

        return {
            "company_name": company_name,
            "ticker": ticker,
            "headline_summary": (
                f"Latest sourced news was retrieved for {company_name}. "
                "Use the items below as a news brief and verify material "
                "developments from primary disclosures before acting."
            ),
            "key_events": key_events,
            "market_impact": (
                "Potential market impact depends on whether the news affects "
                "earnings expectations, margins, deal pipeline, management "
                "guidance, or sector sentiment."
            ),
            "sentiment": "Neutral",
            "risk_factors": risk_factors,
            "confidence_score": 0.0,
            "sources": sources
        }

    # ---------------------------------------------------
    # DETECT NEWS TYPE
    # ---------------------------------------------------

    def detect_news_type(
        self,
        query: str
    ):

        query_lower = query.lower()

        macro_keywords = [

            "economy",
            "inflation",
            "interest rate",
            "fed",
            "rbi",
            "market",
            "stock market",
            "india economy",
            "global economy",
            "gdp",
            "recession",
            "macroeconomic",
            "sensex",
            "nifty",
            "global markets"
        ]

        if any(
            keyword in query_lower
            for keyword in macro_keywords
        ):

            return "MACRO"

        return "COMPANY"

    # ---------------------------------------------------
    # BUILD ENHANCED NEWS QUERY
    # ---------------------------------------------------

    def build_news_query(
        self,
        query: str,
        intelligence: dict
    ):

        enhanced_query = query

        sector = (
            intelligence.get(
                "sector"
            )
        )

        investment_style = (
            intelligence.get(
                "investment_style",
                []
            )
        )

        time_horizon = (
            intelligence.get(
                "time_horizon"
            )
        )

        # ---------------------------------------------------
        # SECTOR ENRICHMENT
        # ---------------------------------------------------

        if sector:

            enhanced_query += (
                f" {sector} sector"
            )

        # ---------------------------------------------------
        # INVESTMENT STYLE
        # ---------------------------------------------------

        if investment_style:

            enhanced_query += (
                " "
                + " ".join(
                    investment_style
                )
            )

        # ---------------------------------------------------
        # TIME HORIZON
        # ---------------------------------------------------

        if time_horizon:

            enhanced_query += (
                f" {time_horizon}"
            )

        # ---------------------------------------------------
        # MARKET CONTEXT
        # ---------------------------------------------------

        enhanced_query += (
            " India NSE BSE"
        )

        return enhanced_query

    # ---------------------------------------------------
    # MAIN NEWS ANALYSIS
    # ---------------------------------------------------

    def analyze(
        self,
        query: str,
        intelligence: dict = None,
        model: str | None = None,
        answer_detail: str = "brief",
        conversation_context: str = ""
    ):

        # ---------------------------------------------------
        # DEFAULT INTELLIGENCE
        # ---------------------------------------------------

        intelligence = (
            intelligence or {}
        )

        # ---------------------------------------------------
        # EXTRACT INTELLIGENCE
        # ---------------------------------------------------

        sector = (
            intelligence.get(
                "sector"
            )
        )

        investment_style = (
            intelligence.get(
                "investment_style",
                []
            )
        )

        risk_profile = (
            intelligence.get(
                "risk_profile"
            )
        )

        time_horizon = (
            intelligence.get(
                "time_horizon"
            )
        )

        analysis_focus = (
            intelligence.get(
                "analysis_focus",
                []
            )
        )
        detail_guidance = answer_detail_guidance(
            answer_detail
        )

        # ---------------------------------------------------
        # ENHANCED QUERY
        # ---------------------------------------------------

        enhanced_query = (
            self.build_news_query(
                query=query,
                intelligence=intelligence
            )
        )

        # ---------------------------------------------------
        # DETECT TYPE
        # ---------------------------------------------------

        news_type = (
            self.detect_news_type(
                query
            )
        )

        # ---------------------------------------------------
        # MACRO FLOW
        # ---------------------------------------------------

        if news_type == "MACRO":

            news_articles = (

                self.news_tool
                .get_general_news(
                    enhanced_query
                )
            )

            company_name = (
                "GLOBAL_MARKETS"
            )

            ticker = "MACRO"

            resolved_entities = 1

        # ---------------------------------------------------
        # COMPANY FLOW
        # ---------------------------------------------------

        else:

            resolved = (

                self.ticker_resolver
                .resolve(query)
            )

            if not resolved:

                return {

                    "success": False,

                    "data": None,

                    "error":
                    "Could not identify stock/company."
                }

            company_name = (
                resolved.get(
                    "company_name",
                    "UNKNOWN"
                )
            )

            ticker = (
                resolved.get(
                    "ticker",
                    "UNKNOWN"
                )
            )

            resolved_entities = 1

            news_articles = (

                self.news_tool
                .get_company_news(
                    company_name
                )
            )

        # ---------------------------------------------------
        # NO NEWS FOUND
        # ---------------------------------------------------

        if (
            not news_articles
            or isinstance(
                news_articles,
                dict
            )
        ):

            return {

                "success": False,

                "data": None,

                "error":
                "No news found."
            }

        # ---------------------------------------------------
        # BUILD CONTEXT
        # ---------------------------------------------------

        news_context = (

            self.news_tool
            .build_news_context(
                news_articles
            )
        )

        # ---------------------------------------------------
        # SOURCES
        # ---------------------------------------------------

        sources = [

            article.get("url")

            for article in news_articles

            if article.get("url")
        ]

        # ---------------------------------------------------
        # TRUSTED SOURCES
        # ---------------------------------------------------

        trusted_domains = [

            "moneycontrol",
            "economictimes",
            "livemint",
            "reuters",
            "business-standard",
            "cnbc",
            "bloomberg",
            "nseindia",
            "bseindia"
        ]

        trusted_sources_count = 0

        for source in sources:

            if any(
                domain in source.lower()
                for domain in trusted_domains
            ):

                trusted_sources_count += 1

        # ---------------------------------------------------
        # PROMPT
        # ---------------------------------------------------

        prompt = f"""
You are an advanced Indian financial news AI.

Analyze the following news articles
and generate institutional-quality
financial intelligence.

TOPIC:
{company_name}

TICKER:
{ticker}

QUERY:
{query}

PRIOR CONVERSATION CONTEXT:
{conversation_context_guidance(conversation_context)}

QUERY INTELLIGENCE:

SECTOR:
{sector}

INVESTMENT STYLE:
{investment_style}

RISK PROFILE:
{risk_profile}

TIME HORIZON:
{time_horizon}

ANALYSIS FOCUS:
{analysis_focus}

NEWS:
{news_context}

ANSWER DETAIL:
{detail_guidance}

IMPORTANT RULES:

- Use ONLY provided news
- Do NOT hallucinate
- Maintain balanced reasoning
- Identify risks and opportunities
- Explain possible market implications
- Detect overall sentiment
- Align analysis with investment style
- Align analysis with time horizon
- Avoid hype/speculation
- Avoid guaranteed outcomes
- Maintain concise institutional tone
- For Indian listed companies, express monetary values in INR crore or
  INR lakh crore. Do not leave revenue, income, or market cap in USD.

Return ONLY valid JSON.

FORMAT:

{{
    "company_name": "",

    "ticker": "",

    "headline_summary": "",

    "key_events": [],

    "market_impact": "",

    "sentiment": "",

    "risk_factors": [],

    "confidence_score": 0.0,

    "sources": []
}}
"""

        # ---------------------------------------------------
        # LLM CALL
        # ---------------------------------------------------

        llm_success = True

        try:

            raw_output = (

                self.groq.generate_raw(

                    prompt=prompt,

                    temperature=0.2,

                    max_tokens=answer_detail_tokens(
                        answer_detail,
                        brief_tokens=1400,
                        detailed_tokens=2200
                    ),

                    model=model
                )
            )

        except Exception as e:

            return {

                "success": False,

                "data": None,

                "error":
                safe_provider_error(
                    e,
                    "news_analyze"
                )
            }

        if is_provider_error_text(
            raw_output
        ):

            return {
                "success": False,
                "data": None,
                "error": raw_output
            }

        # ---------------------------------------------------
        # SAFE JSON PARSE
        # ---------------------------------------------------

        parsed = (
            JSONParser.parse(
                raw_output
            )
        )

        # ---------------------------------------------------
        # PARSE FAILURE
        # ---------------------------------------------------

        if not parsed:

            llm_success = False

            parsed = self.build_fallback_response(
                company_name=company_name,
                ticker=ticker,
                news_articles=news_articles,
                sources=sources
            )

        # ---------------------------------------------------
        # FORCE CONSISTENCY
        # ---------------------------------------------------

        parsed[
            "company_name"
        ] = company_name

        parsed[
            "ticker"
        ] = ticker

        parsed[
            "sources"
        ] = sources

        parsed = (
            FinancialNormalizer
            .normalize_usd_amounts(
                parsed,
                USD_TO_INR_RATE
            )
        )

        # ---------------------------------------------------
        # QUERY COMPLEXITY
        # ---------------------------------------------------

        query_complexity = (
            self.confidence_engine
            .detect_query_complexity(

                companies=[company_name],

                has_news=True,

                has_comparison=False,

                has_discovery=False,

                has_macro=(
                    news_type == "MACRO"
                )
            )
        )

        # ---------------------------------------------------
        # DYNAMIC CONFIDENCE
        # ---------------------------------------------------

        confidence_result = (
            self.confidence_engine
            .calculate_confidence(

                retrieval_success_count=
                len(news_articles),

                retrieval_total_count=
                max(
                    len(news_articles),
                    1
                ),

                resolved_entities=
                resolved_entities,

                requested_entities=1,

                data_fields_present=
                len(parsed.keys()),

                expected_data_fields=8,

                llm_parse_success=
                llm_success,

                schema_validation_success=True,

                trusted_sources_count=
                trusted_sources_count,

                total_sources_count=max(
                    len(sources),
                    1
                ),

                query_complexity=
                query_complexity,

                ambiguity_detected=False,

                api_failures=0
            )
        )

        parsed[
            "confidence_score"
        ] = confidence_result[
            "confidence_score"
        ]

        parsed[
            "confidence_breakdown"
        ] = confidence_result[
            "breakdown"
        ]

        # ---------------------------------------------------
        # SCHEMA VALIDATION
        # ---------------------------------------------------

        try:

            validated = (
                NewsResponse(
                    **parsed
                )
            )

            return {

                "success": True,

                "data":
                validated.model_dump(),

                "error": None
            }

        except Exception as e:

            return {

                "success": False,

                "data": None,

                "error":
                f"Schema validation failed: {str(e)}"
            }
