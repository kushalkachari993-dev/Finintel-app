import json
import re

from backend.tools.tavily_search_tool import (
    TavilySearchTool
)

from backend.llm.groq_provider import (
    GroqProvider
)

from backend.utils.json_parser import (
    JSONParser
)

from backend.schemas.discovery_schema import (
    DiscoveryResponse
)

from backend.utils.retrieval_filter import (
    RetrievalFilter
)

from backend.utils.confidence_engine import (
    ConfidenceEngine
)
from backend.agents.detail_guidance import (
    answer_detail_guidance,
    answer_detail_tokens
)
from backend.utils.provider_errors import (
    is_provider_error_text,
    safe_provider_error
)


class DiscoveryAgent:

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        self.search_tool = (
            TavilySearchTool()
        )

        self.groq = (
            GroqProvider()
        )

        self.confidence_engine = (
            ConfidenceEngine()
        )

    @staticmethod
    def is_noisy_source_text(
        text: str
    ) -> bool:
        if not text:
            return True

        pipe_count = text.count(
            "|"
        )
        digit_count = sum(
            character.isdigit()
            for character in text
        )
        word_count = len(
            text.split()
        )

        social_noise = any(
            marker in text.lower()
            for marker in [
                "whatsapp",
                "facebook",
                "twitter",
                "linkedin",
                "s.no",
                "cmp rs",
                "mar cap",
                "qtr sales",
                "profit var"
            ]
        )

        return (
            social_noise
            or pipe_count >= 4
            or (
                word_count > 0
                and digit_count / max(len(text), 1) > 0.22
            )
        )

    @staticmethod
    def clean_source_text(
        text: str
    ) -> str:
        cleaned = re.sub(
            r"\s+",
            " ",
            text or ""
        ).strip()
        cleaned = re.sub(
            r"\b(Whatsapp|Facebook|Twitter|LinkedIn)\b",
            "",
            cleaned,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned
        ).strip(" -|")

        return cleaned[:260]

    @staticmethod
    def build_fallback_response(
        query: str,
        context: list,
        intelligence: dict | None = None
    ) -> dict:
        intelligence = intelligence or {}
        sector = intelligence.get(
            "sector"
        )
        investment_style = intelligence.get(
            "investment_style",
            []
        )
        analysis_focus = intelligence.get(
            "analysis_focus",
            []
        )

        source_points = []

        for item in context[:5]:
            title = item.get(
                "title",
                ""
            )
            content = item.get(
                "content",
                ""
            )
            candidate = f"{title}: {content}" if title and content else title or content

            if self_text := DiscoveryAgent.clean_source_text(candidate):
                if not DiscoveryAgent.is_noisy_source_text(self_text):
                    source_points.append(
                        self_text
                    )

        focus_text = (
            ", ".join(analysis_focus).lower()
            if analysis_focus
            else "valuation quality"
        )
        style_text = (
            ", ".join(investment_style).lower()
            if investment_style
            else "screening"
        )
        sector_text = (
            f"{sector} "
            if sector
            else ""
        )

        key_points = [
            (
                f"Use this as a {style_text} screen for Indian {sector_text}"
                f"stocks, not as a buy list. Shortlist only after checking "
                f"{focus_text}, earnings quality, debt, and recent results."
            ),
            (
                "Prefer companies where valuation comfort is supported by "
                "stable revenue, margins, cash generation, and credible growth "
                "rather than only a low P/E or low price."
            ),
            (
                "For Indian IT names, watch demand slowdown, client spending "
                "cycles, margin pressure, currency movement, and deal pipeline "
                "before assuming a stock is undervalued."
            )
        ]

        key_points.extend(
            source_points[:2]
        )

        return {
            "query_type": "DISCOVERY",
            "summary": (
                f"Found market sources for Indian {sector_text}stock discovery. "
                "Treat the result as a screening starting point: validate each "
                "candidate with current fundamentals, valuation, earnings trend, "
                "and risks before shortlisting."
            ),
            "key_points": key_points,
            "mentioned_companies": [],
            "confidence_score": 0.0,
            "sources_used": []
        }

    # ---------------------------------------------------
    # BUILD ENHANCED SEARCH QUERY
    # ---------------------------------------------------

    def build_search_query(
        self,
        query: str,
        intelligence: dict
    ):

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

        analysis_focus = (
            intelligence.get(
                "analysis_focus",
                []
            )
        )

        enhanced_query = query

        # ---------------------------------------------------
        # SECTOR ENRICHMENT
        # ---------------------------------------------------

        if sector:

            enhanced_query += (
                f" Indian {sector} sector"
            )

        # ---------------------------------------------------
        # INVESTMENT STYLE ENRICHMENT
        # ---------------------------------------------------

        if investment_style:

            enhanced_query += (
                " "
                + " ".join(
                    investment_style
                )
            )

        # ---------------------------------------------------
        # TIME HORIZON ENRICHMENT
        # ---------------------------------------------------

        if time_horizon:

            enhanced_query += (
                f" {time_horizon}"
            )

        # ---------------------------------------------------
        # ANALYSIS FOCUS ENRICHMENT
        # ---------------------------------------------------

        if analysis_focus:

            enhanced_query += (
                " "
                + " ".join(
                    analysis_focus
                )
            )

        # ---------------------------------------------------
        # MARKET CONTEXT
        # ---------------------------------------------------

        enhanced_query += (
            " Indian stock market NSE BSE"
        )

        return enhanced_query

    # ---------------------------------------------------
    # MAIN DISCOVERY METHOD
    # ---------------------------------------------------

    def discover(
        self,
        query: str,
        intelligence: dict = None,
        model: str | None = None,
        answer_detail: str = "brief"
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
        # ENHANCED SEARCH QUERY
        # ---------------------------------------------------

        enhanced_query = (
            self.build_search_query(
                query=query,
                intelligence=intelligence
            )
        )

        # ---------------------------------------------------
        # SEARCH WEB
        # ---------------------------------------------------

        context = (
            self.search_tool.search(

                query=enhanced_query,

                max_results=7
            )
        )

        # ---------------------------------------------------
        # HANDLE SEARCH FAILURE
        # ---------------------------------------------------

        if not context:

            return {

                "success": False,

                "data": None,

                "error":
                "No search results found."
            }

        # ---------------------------------------------------
        # HANDLE SEARCH ERRORS
        # ---------------------------------------------------

        if (
            isinstance(context, list)
            and len(context) > 0
            and "error" in context[0]
        ):

            return {

                "success": False,

                "data": None,

                "error":
                context[0]["error"]
            }

        # ---------------------------------------------------
        # RETRIEVAL FILTERING
        # ---------------------------------------------------

        filtered_context = (
            RetrievalFilter.filter_results(
                context
            )
        )

        # ---------------------------------------------------
        # VALIDATE FILTERED CONTEXT
        # ---------------------------------------------------

        if not filtered_context:

            filtered_context = context

        # ---------------------------------------------------
        # BUILD CONTEXT
        # ---------------------------------------------------

        context_text = ""

        sources_used = []

        trusted_sources_count = 0

        mentioned_companies = []

        trusted_domains = [

            "moneycontrol",
            "screener",
            "economictimes",
            "livemint",
            "reuters",
            "business-standard",
            "tickertape",
            "groww",
            "nseindia",
            "bseindia"
        ]

        for item in filtered_context:

            title = item.get(
                "title",
                ""
            )

            content = item.get(
                "content",
                ""
            )

            url = item.get(
                "url",
                ""
            )

            context_text += (

                f"Title: {title}\n"

                f"Content: {content}\n\n"
            )

            if url:

                sources_used.append(
                    url
                )

                # -------------------------------------------
                # TRUSTED SOURCE DETECTION
                # -------------------------------------------

                if any(
                    domain in url.lower()
                    for domain in trusted_domains
                ):

                    trusted_sources_count += 1

        # ---------------------------------------------------
        # PROMPT
        # ---------------------------------------------------

        prompt = f"""
You are a financial discovery analyst
specialized in Indian equity markets.

IMPORTANT RULES:

- Use ONLY provided web context
- Do NOT hallucinate
- Do NOT invent companies
- Maintain balanced reasoning
- Mention both opportunities and risks
- Avoid hype/speculation
- Avoid guaranteed returns
- Use institutional-quality reasoning

USER QUERY:
{query}

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

ENHANCED SEARCH QUERY:
{enhanced_query}

WEB CONTEXT:
{context_text}

ANSWER DETAIL:
{detail_guidance}

IMPORTANT INSTRUCTIONS:

- Align recommendations with investment style
- Align reasoning with time horizon
- Focus especially on:
{analysis_focus}
- Mention sector-specific risks
- Mention valuation concerns where relevant
- Mention quality and financial stability
- Maintain concise analytical tone

Return ONLY valid JSON.

FORMAT:

{{
    "query_type": "DISCOVERY",

    "summary": "",

    "key_points": [],

    "mentioned_companies": [],

    "confidence_score": 0.0,

    "sources_used": []
}}
"""

        # ---------------------------------------------------
        # LLM SYNTHESIS
        # ---------------------------------------------------

        llm_success = True

        try:

            raw_response = (
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
                    "discovery_discover"
                )
            }

        if is_provider_error_text(
            raw_response
        ):

            return {
                "success": False,
                "data": None,
                "error": raw_response
            }

        # ---------------------------------------------------
        # SAFE JSON PARSING
        # ---------------------------------------------------

        parsed = (
            JSONParser.parse(
                raw_response
            )
        )

        # ---------------------------------------------------
        # PARSE FAILURE
        # ---------------------------------------------------

        if not parsed:

            llm_success = False

            parsed = self.build_fallback_response(
                query=query,
                context=filtered_context,
                intelligence=intelligence
            )

        # ---------------------------------------------------
        # FORCE SOURCES
        # ---------------------------------------------------

        parsed[
            "sources_used"
        ] = sources_used

        # ---------------------------------------------------
        # CLEAN COMPANIES
        # ---------------------------------------------------

        mentioned_companies = (
            parsed.get(
                "mentioned_companies",
                []
            )
        )

        if not isinstance(
            mentioned_companies,
            list
        ):

            mentioned_companies = []

        # ---------------------------------------------------
        # DYNAMIC CONFIDENCE
        # ---------------------------------------------------

        query_complexity = (
            self.confidence_engine
            .detect_query_complexity(

                companies=
                mentioned_companies,

                has_discovery=True,

                has_news=(
                    "news"
                    in query.lower()
                ),

                has_comparison=(
                    "compare"
                    in query.lower()
                ),

                has_macro=False
            )
        )

        confidence_result = (
            self.confidence_engine
            .calculate_confidence(

                retrieval_success_count=
                len(filtered_context),

                retrieval_total_count=
                7,

                resolved_entities=
                len(mentioned_companies),

                requested_entities=max(
                    len(mentioned_companies),
                    1
                ),

                data_fields_present=
                len(parsed.keys()),

                expected_data_fields=6,

                llm_parse_success=
                llm_success,

                schema_validation_success=True,

                trusted_sources_count=
                trusted_sources_count,

                total_sources_count=max(
                    len(sources_used),
                    1
                ),

                query_complexity=
                query_complexity,

                ambiguity_detected=(
                    "news" in query.lower()
                    and
                    "compare" in query.lower()
                ),

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
                DiscoveryResponse(
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
