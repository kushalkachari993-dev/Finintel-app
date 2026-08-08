import json
import logging
from concurrent.futures import ThreadPoolExecutor

from groq import Groq

from backend.config.settings import (
    GROQ_API_KEY,
    GROQ_MODEL
)

from backend.tools.stock_data_tool import (
    StockDataTool
)

from backend.tools.ticker_resolver import (
    TickerResolver
)

from backend.tools.financial_metrics_interpreter import (
    FinancialMetricsInterpreter
)

from backend.tools.company_context_tool import (
    CompanyContextTool
)

from backend.utils.json_parser import (
    JSONParser
)

from backend.schemas.comparison_schema import (
    ComparisonResponse
)

from backend.utils.confidence_engine import (
    ConfidenceEngine
)
from backend.agents.detail_guidance import (
    answer_detail_guidance,
    answer_detail_tokens
)
from backend.utils.provider_errors import (
    safe_provider_error
)


logger = logging.getLogger(__name__)


class ComparisonAgent:

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        self.client = Groq(
            api_key=GROQ_API_KEY
        )

        self.stock_tool = (
            StockDataTool()
        )

        self.ticker_resolver = (
            TickerResolver()
        )

        self.financial_interpreter = (
            FinancialMetricsInterpreter()
        )

        self.confidence_engine = (
            ConfidenceEngine()
        )

        self.company_context_tool = (
            CompanyContextTool()
        )

    # ---------------------------------------------------
    # EXTRACT COMPANIES
    # ---------------------------------------------------

    def extract_companies(
        self,
        query: str
    ):

        cleaned_query = (
            query
            .replace("Compare", "")
            .replace("compare", "")
            .replace(" versus ", ",")
            .replace(" vs ", ",")
            .replace(" and ", ",")
        )

        raw_candidates = [

            item.strip()

            for item in cleaned_query.split(",")

            if item.strip()
        ]

        blocked = {

            "stocks",
            "stock",
            "companies",
            "company",
            "best",
            "top",
            "undervalued",
            "overvalued",
            "long term",
            "short term",
            "investment",
            "fundamentally",
            "strong",
            "growth",
            "value",
            "safe",
            "india",
            "indian"
        }

        final_companies = []

        for candidate in raw_candidates:

            cleaned = candidate.strip()

            if cleaned.lower() not in blocked:

                final_companies.append(
                    cleaned
                )

        return final_companies

    # ---------------------------------------------------
    # BUILD DISCOVERY CANDIDATES
    # ---------------------------------------------------

    def build_discovery_candidates(
        self,
        intelligence: dict
    ):

        sector = intelligence.get(
            "sector"
        )

        investment_style = (
            intelligence.get(
                "investment_style",
                []
            )
        )

        # ---------------------------------------------------
        # IT
        # ---------------------------------------------------

        if sector == "IT":

            if "VALUE" in investment_style:

                return [
                    "Infosys",
                    "HCLTech",
                    "Tech Mahindra"
                ]

            return [
                "TCS",
                "Infosys",
                "HCLTech"
            ]

        # ---------------------------------------------------
        # BANKING
        # ---------------------------------------------------

        elif sector == "BANKING":

            return [
                "HDFC Bank",
                "ICICI Bank",
                "Axis Bank"
            ]

        # ---------------------------------------------------
        # PHARMA
        # ---------------------------------------------------

        elif sector == "PHARMA":

            return [
                "Sun Pharma",
                "Dr Reddys",
                "Cipla"
            ]

        # ---------------------------------------------------
        # FMCG
        # ---------------------------------------------------

        elif sector == "FMCG":

            return [
                "HUL",
                "ITC",
                "Nestle India"
            ]

        # ---------------------------------------------------
        # AUTOMOBILE
        # ---------------------------------------------------

        elif sector == "AUTOMOBILE":

            return [
                "Maruti",
                "Tata Motors",
                "Mahindra"
            ]

        return []

    # ---------------------------------------------------
    # RESOLVE COMPANIES
    # ---------------------------------------------------

    def resolve_companies(
        self,
        company_queries: list
    ):

        resolved_companies = []

        max_workers = min(
            4,
            max(
                len(company_queries),
                1
            )
        )

        with ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:

            resolved_results = executor.map(
                self.ticker_resolver.resolve,
                company_queries
            )

        for resolved in resolved_results:

            if resolved:

                resolved_companies.append(
                    resolved
                )

        return resolved_companies

    # ---------------------------------------------------
    # FETCH ONE COMPANY DATA
    # ---------------------------------------------------

    def fetch_single_company_data(
        self,
        company: dict
    ):

        ticker = company.get(
            "ticker"
        )

        try:

            stock_data = (

                self.stock_tool
                .get_stock_data(
                    ticker
                )
            )

            if (
                stock_data
                and "error" not in stock_data
            ):

                interpretation = (

                    self.financial_interpreter
                    .generate_interpretation(
                        stock_data
                    )
                )

                return {

                    "success":
                    True,

                    "data": {

                        "company_name":
                        company.get(
                            "company_name"
                        ),

                        "ticker":
                        ticker,

                        "stock_data":
                        stock_data,

                        "interpretation":
                        interpretation
                    }
                }

            return {

                "success":
                False,

                "data":
                None
            }

        except Exception:

            logger.exception(
                "comparison_company_fetch_failed ticker=%s",
                ticker
            )

            return {

                "success":
                False,

                "data":
                None
            }

    # ---------------------------------------------------
    # FETCH COMPANY DATA
    # ---------------------------------------------------

    def fetch_company_data(
        self,
        resolved_companies: list
    ):

        comparison_data = []

        successful_fetches = 0
        api_failures = 0

        max_workers = min(
            4,
            max(
                len(resolved_companies),
                1
            )
        )

        with ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:

            fetch_results = executor.map(
                self.fetch_single_company_data,
                resolved_companies
            )

        for result in fetch_results:

            if result.get(
                "success"
            ):

                successful_fetches += 1
                comparison_data.append(
                    result["data"]
                )

            else:

                api_failures += 1

        return {

            "comparison_data":
            comparison_data,

            "successful_fetches":
            successful_fetches,

            "api_failures":
            api_failures
        }

    # ---------------------------------------------------
    # PARTIAL DATA FALLBACK
    # ---------------------------------------------------

    def build_partial_data_response(
        self,
        query: str,
        company_queries: list,
        resolved_companies: list,
        comparison_data: list,
        successful_fetches: int,
        api_failures: int,
        analysis_focus: list | None = None
    ):

        analysis_focus = (
            analysis_focus or []
        )

        available_by_ticker = {
            company.get("ticker"):
            company
            for company in comparison_data
        }

        companies_compared = [
            company.get(
                "company_name"
            )
            or company.get(
                "ticker"
            )
            or str(company)
            for company in resolved_companies
        ]

        comparative_analysis = []
        strengths = {}
        risks = {}

        for company in resolved_companies:

            company_name = (
                company.get(
                    "company_name"
                )
                or company.get(
                    "ticker"
                )
                or "Company"
            )

            ticker = company.get(
                "ticker",
                "ticker unavailable"
            )

            available = available_by_ticker.get(
                company.get(
                    "ticker"
                )
            )

            if available:

                stock_data = (
                    available.get(
                        "stock_data",
                        {}
                    )
                )

                comparative_analysis.append(
                    (
                        f"{company_name} ({ticker}) was resolved and "
                        "live market data was partially available. "
                        f"Current price: {stock_data.get('current_price', 'not available')}; "
                        f"P/E: {stock_data.get('pe_ratio', 'not available')}; "
                        f"ROE: {stock_data.get('roe', 'not available')}."
                    )
                )

                strengths[company_name] = [
                    "Company entity and ticker were resolved successfully.",
                    "Some live market data was available for this company."
                ]

                risks[company_name] = [
                    (
                        "Comparison reliability is limited because complete "
                        "peer data was not available for every company."
                    )
                ]

            else:

                comparative_analysis.append(
                    (
                        f"{company_name} ({ticker}) was resolved, but "
                        "live company financial data was unavailable or "
                        "incomplete during this request."
                    )
                )

                strengths[company_name] = [
                    "Company entity and ticker were resolved successfully."
                ]

                risks[company_name] = [
                    (
                        "Live market and financial metrics were unavailable "
                        "or incomplete during this request."
                    )
                ]

        confidence_score = (
            0.45
            if successful_fetches > 0
            else 0.3
        )

        confidence_breakdown = {
            "retrieval_score":
            round(
                successful_fetches / max(
                    len(company_queries),
                    1
                ),
                2
            ),
            "resolved_entities":
            len(resolved_companies),
            "requested_entities":
            len(company_queries),
            "api_failures":
            api_failures,
            "fallback_used":
            True
        }

        parsed = {
            "comparison_type":
            (
                analysis_focus[0]
                if analysis_focus
                else "GENERAL"
            ),

            "companies_compared":
            companies_compared,

            "summary":
            (
                "The companies were identified, but complete live financial "
                "data was not available for at least two companies. This is "
                "a partial comparison focused on data availability rather "
                "than a full investment-quality peer analysis."
            ),

            "comparative_analysis":
            comparative_analysis,

            "strengths":
            strengths,

            "risks":
            risks,

            "winner_summary":
            (
                "No winner can be identified from the available data. "
                "Retry when live data is available or generate a qualitative "
                "report for broader context."
            ),

            "balanced_view":
            (
                "A fair peer comparison requires current metrics for both "
                "companies. FinIntel found the companies, but live data was "
                "insufficient for a complete comparison in this request."
            ),

            "confidence_score":
            confidence_score,

            "confidence_breakdown":
            confidence_breakdown,

            "sources_used":
            [],

            "disclaimer":
            (
                "This partial comparison is for educational purposes only "
                "and is not investment advice."
            )
        }

        validated = (
            ComparisonResponse(
                **parsed
            )
        )

        logger.warning(
            "comparison_partial_data_fallback query=%r companies=%s successful_fetches=%s api_failures=%s",
            query,
            companies_compared,
            successful_fetches,
            api_failures
        )

        return {
            "success":
            True,

            "data":
            validated.model_dump(),

            "error":
            None
        }

    # ---------------------------------------------------
    # FETCH COMPANY CONTEXTS
    # ---------------------------------------------------

    def fetch_company_contexts(
        self,
        comparison_data: list
    ):

        def fetch_context(company):

            return (
                company,
                self.company_context_tool
                .get_company_context(
                    company_name=company[
                        "company_name"
                    ],
                    ticker=company[
                        "ticker"
                    ],
                    max_results=3
                )
            )

        max_workers = min(
            4,
            max(
                len(comparison_data),
                1
            )
        )

        with ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:

            return list(
                executor.map(
                    fetch_context,
                    comparison_data
                )
            )

    # ---------------------------------------------------
    # MAIN COMPARISON METHOD
    # ---------------------------------------------------

    def compare(
        self,
        query: str,
        intelligence: dict = None,
        model: str | None = None,
        answer_detail: str = "brief"
    ):

        intelligence = (
            intelligence or {}
        )

        analysis_focus = (
            intelligence.get(
                "analysis_focus",
                []
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

        sector = (
            intelligence.get(
                "sector"
            )
        )
        detail_guidance = answer_detail_guidance(
            answer_detail
        )

        # ---------------------------------------------------
        # EXTRACT COMPANIES
        # ---------------------------------------------------

        company_queries = (
            self.extract_companies(
                query
            )
        )

        # ---------------------------------------------------
        # FALLBACK TO QUERY INTELLIGENCE
        # ---------------------------------------------------

        if len(company_queries) < 2:

            extracted = (
                intelligence.get(
                    "companies",
                    []
                )
            )

            if len(extracted) >= 2:

                company_queries = (
                    extracted
                )

        # ---------------------------------------------------
        # DISCOVERY FALLBACK
        # ---------------------------------------------------

        if len(company_queries) < 2:

            company_queries = (
                self.build_discovery_candidates(
                    intelligence
                )
            )

        # ---------------------------------------------------
        # FINAL VALIDATION
        # ---------------------------------------------------

        if len(company_queries) < 2:

            return {

                "success": False,

                "data": None,

                "error":
                (
                    "Could not identify enough "
                    "companies for comparison."
                )
            }

        # ---------------------------------------------------
        # RESOLVE COMPANIES
        # ---------------------------------------------------

        resolved_companies = (
            self.resolve_companies(
                company_queries
            )
        )

        if len(resolved_companies) < 2:

            return {

                "success": False,

                "data": None,

                "error":
                (
                    "Failed to resolve "
                    "multiple companies."
                )
            }

        # ---------------------------------------------------
        # FETCH COMPANY DATA
        # ---------------------------------------------------

        fetch_result = (
            self.fetch_company_data(
                resolved_companies
            )
        )

        comparison_data = (
            fetch_result[
                "comparison_data"
            ]
        )

        successful_fetches = (
            fetch_result[
                "successful_fetches"
            ]
        )

        api_failures = (
            fetch_result[
                "api_failures"
            ]
        )

        # ---------------------------------------------------
        # VALIDATION
        # ---------------------------------------------------

        if len(comparison_data) < 2:

            return self.build_partial_data_response(
                query=query,
                company_queries=company_queries,
                resolved_companies=resolved_companies,
                comparison_data=comparison_data,
                successful_fetches=successful_fetches,
                api_failures=api_failures,
                analysis_focus=analysis_focus
            )

        # ---------------------------------------------------
        # TRUSTED COMPANY CONTEXT
        # ---------------------------------------------------

        company_contexts = []
        sources_used = []

        for company, context_result in self.fetch_company_contexts(
            comparison_data
        ):

            context_text = context_result.get(
                "context_text",
                ""
            )

            if context_text:

                company_contexts.append({

                    "company_name":
                    company["company_name"],

                    "ticker":
                    company["ticker"],

                    "context":
                    context_text
                })

            sources_used.extend(
                context_result.get(
                    "sources_used",
                    []
                )
            )

        sources_used = list(
            dict.fromkeys(sources_used)
        )

        # ---------------------------------------------------
        # SYSTEM PROMPT
        # ---------------------------------------------------

        system_prompt = """
You are FinIntel AI,
an institutional-grade
Indian equity comparison analyst.

IMPORTANT RULES:

- Use ONLY provided data
- Use ONLY provided interpretations
- Do NOT hallucinate
- Do NOT invent metrics
- Maintain balanced reasoning
- Mention strengths and risks
- Avoid hype/speculation
- Avoid guaranteed outcomes
- Maintain professional tone

Return ONLY valid JSON.
Do NOT return markdown.
"""

        # ---------------------------------------------------
        # USER PROMPT
        # ---------------------------------------------------

        user_prompt = f"""
Perform a structured comparison.

USER QUERY:
{query}

QUERY INTELLIGENCE:

ANALYSIS FOCUS:
{analysis_focus}

INVESTMENT STYLE:
{investment_style}

RISK PROFILE:
{risk_profile}

TIME HORIZON:
{time_horizon}

SECTOR:
{sector}

COMPANY DATA:
{json.dumps(comparison_data, indent=2)}

TRUSTED COMPANY CONTEXT:
{json.dumps(company_contexts, indent=2)}

ANSWER DETAIL:
{detail_guidance}

Return ONLY valid JSON.

FORMAT:

{{
    "comparison_type": "",

    "companies_compared": [],

    "summary": "",

    "comparative_analysis": [
        "",
        ""
    ],

    "strengths": {{}},

    "risks": {{}},

    "winner_summary": "",

    "balanced_view": "",

    "confidence_score": 0.0,

    "sources_used": [],

    "disclaimer": ""
}}
"""

        # ---------------------------------------------------
        # LLM CALL
        # ---------------------------------------------------

        llm_parse_success = True
        schema_validation_success = True

        try:

            response = (
                self.client.chat.completions.create(

                    model=
                    model or GROQ_MODEL,

                    messages=[

                        {
                            "role": "system",
                            "content": system_prompt
                        },

                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],

                    temperature=0.2,

                    max_tokens=answer_detail_tokens(
                        answer_detail,
                        brief_tokens=1800,
                        detailed_tokens=2800
                    ),
                )
            )

            raw_output = (
                response
                .choices[0]
                .message.content
            )

        except Exception as e:

            return {

                "success": False,

                "data": None,

                "error":
                safe_provider_error(
                    e,
                    "comparison_compare"
                )
            }

        # ---------------------------------------------------
        # JSON PARSE
        # ---------------------------------------------------

        parsed = (
            JSONParser.parse(
                raw_output
            )
        )

        if not parsed:

            llm_parse_success = False

            return {

                "success": False,

                "data": None,

                "error":
                "Failed to parse comparison response."
            }

        # ---------------------------------------------------
        # FORCE CONSISTENCY
        # ---------------------------------------------------

        parsed[
            "companies_compared"
        ] = [

            company["company_name"]

            for company in comparison_data
        ]

        if not parsed.get(
            "comparison_type"
        ):

            parsed[
                "comparison_type"
            ] = (
                analysis_focus[0]
                if analysis_focus
                else "GENERAL"
            )

        # ---------------------------------------------------
        # FIX comparative_analysis TYPE
        # ---------------------------------------------------

        if isinstance(
            parsed.get(
                "comparative_analysis"
            ),
            str
        ):

            parsed[
                "comparative_analysis"
            ] = [

                parsed[
                    "comparative_analysis"
                ]
            ]

        # ---------------------------------------------------
        # DEFAULTS
        # ---------------------------------------------------

        parsed.setdefault(
            "winner_summary",
            "No definitive winner identified."
        )

        parsed.setdefault(
            "balanced_view",
            (
                "Companies have varying strengths "
                "depending on valuation, growth, "
                "profitability and risk profile."
            )
        )

        parsed.setdefault(
            "strengths",
            {}
        )

        parsed.setdefault(
            "risks",
            {}
        )

        parsed.setdefault(
            "disclaimer",
            (
                "This comparison is for educational "
                "purposes only and not investment advice."
            )
        )

        parsed[
            "sources_used"
        ] = sources_used

        # ---------------------------------------------------
        # DYNAMIC CONFIDENCE ENGINE
        # ---------------------------------------------------

        expected_fields = 8

        present_fields = sum([

            1 for key in [

                "summary",
                "comparative_analysis",
                "winner_summary",
                "balanced_view",
                "strengths",
                "risks",
                "comparison_type",
                "disclaimer"
            ]

            if parsed.get(key)
        ])

        complexity = (
            self.confidence_engine
            .detect_query_complexity(

                companies=company_queries,

                has_comparison=True,

                has_discovery=(
                    len(
                        intelligence.get(
                            "companies",
                            []
                        )
                    ) == 0
                )
            )
        )

        confidence_result = (
            self.confidence_engine
            .calculate_confidence(

                retrieval_success_count=
                successful_fetches,

                retrieval_total_count=
                len(company_queries),

                resolved_entities=
                len(resolved_companies),

                requested_entities=
                len(company_queries),

                data_fields_present=
                present_fields,

                expected_data_fields=
                expected_fields,

                llm_parse_success=
                llm_parse_success,

                schema_validation_success=
                schema_validation_success,

                trusted_sources_count=
                (
                    successful_fetches
                    + len(sources_used)
                ),

                total_sources_count=
                (
                    len(company_queries)
                    + max(
                        len(sources_used),
                        1
                    )
                ),

                query_complexity=
                complexity,

                ambiguity_detected=False,

                api_failures=
                api_failures
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
                ComparisonResponse(
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

            schema_validation_success = False

            return {

                "success": False,

                "data": None,

                "error":
                (
                    "Schema validation failed: "
                    f"{str(e)}"
                )
            }
