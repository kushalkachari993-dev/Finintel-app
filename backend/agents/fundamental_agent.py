import json

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

from backend.schemas.fundamental_schema import (
    FundamentalResponse
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


class FundamentalAgent:

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
    # MAIN ANALYSIS METHOD
    # ---------------------------------------------------

    def analyze(
        self,
        query: str,
        intelligence: dict = None,
        model: str | None = None,
        answer_detail: str = "brief"
    ):

        intelligence = (
            intelligence or {}
        )

        # ---------------------------------------------------
        # RESOLVE COMPANY
        # ---------------------------------------------------

        resolved = (
            self.ticker_resolver.resolve(
                query
            )
        )

        if not resolved:

            return {

                "success": False,

                "data": None,

                "error":
                "Could not identify stock/company."
            }

        ticker = resolved.get(
            "ticker"
        )

        company_name = resolved.get(
            "company_name"
        )

        # ---------------------------------------------------
        # FETCH STOCK DATA
        # ---------------------------------------------------

        stock_data = (
            self.stock_tool
            .get_stock_data(
                ticker
            )
        )

        if not stock_data:

            return {

                "success": False,

                "data": None,

                "error":
                "Failed to fetch stock data."
            }

        if "error" in stock_data:

            return {

                "success": False,

                "data": None,

                "error":
                stock_data["error"]
            }

        # ---------------------------------------------------
        # INTERPRETATIONS
        # ---------------------------------------------------

        interpretation = (

            self.financial_interpreter
            .generate_interpretation(
                stock_data
            )
        )

        # ---------------------------------------------------
        # TRUSTED COMPANY CONTEXT
        # ---------------------------------------------------

        context_result = (
            self.company_context_tool
            .get_company_context(
                company_name=company_name,
                ticker=ticker
            )
        )

        company_context = context_result.get(
            "context_text",
            ""
        )

        sources_used = context_result.get(
            "sources_used",
            []
        )

        # ---------------------------------------------------
        # QUERY INTELLIGENCE
        # ---------------------------------------------------

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

        analysis_type = (
            analysis_focus[0]
            if analysis_focus
            else "GENERAL"
        )
        detail_guidance = answer_detail_guidance(
            answer_detail
        )

        # ---------------------------------------------------
        # PROMPTS
        # ---------------------------------------------------

        system_prompt = """
You are FinIntel AI,
a specialized Indian stock market
fundamental analysis assistant.

IMPORTANT RULES:

- Use ONLY provided financial data
- Use ONLY provided interpretations
- Do NOT hallucinate
- Do NOT invent financial numbers
- Maintain balanced reasoning
- Mention both positives and risks
- Avoid hype/speculation
- Avoid guaranteed returns
- Avoid target prices
- Maintain professional institutional tone
- Keep reasoning concise and analytical

Return ONLY valid JSON.
Do NOT return markdown.
"""

        user_prompt = f"""
Perform a structured Indian stock market
fundamental analysis.

USER QUERY:
{query}

COMPANY:
{company_name}

TICKER:
{ticker}

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

RAW FINANCIAL DATA:
{json.dumps(stock_data, indent=2)}

PRE-COMPUTED INTERPRETATIONS:
{json.dumps(interpretation, indent=2)}

TRUSTED COMPANY CONTEXT:
{company_context if company_context else "No trusted company context retrieved."}

ANSWER DETAIL:
{detail_guidance}

IMPORTANT INSTRUCTIONS:

- Use the provided interpretations directly
- Use trusted company context only as supporting business/source context
- Do NOT reinterpret ratios independently
- Do NOT invent facts beyond the supplied financial data and context
- Align reasoning with the user's investment style
- Align reasoning with the user's time horizon
- Focus especially on:
{analysis_type}
analysis
- Maintain institutional-quality reasoning
- Mention both strengths and risks
- Avoid speculation

Return ONLY valid JSON
using this schema:

{{
    "company_name": "...",

    "ticker": "...",

    "analysis_type": "...",

    "business_overview": "...",

    "financial_strengths": [
        "...",
        "..."
    ],

    "financial_risks": [
        "...",
        "..."
    ],

    "valuation_commentary": "...",

    "overall_view": "...",

    "confidence_score": 0.0,

    "sources_used": [],

    "disclaimer": "..."
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
                        brief_tokens=1400,
                        detailed_tokens=2300
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
                    "fundamental_analyze"
                )
            }

        # ---------------------------------------------------
        # SAFE JSON PARSING
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
                "Failed to parse model response."
            }

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
            "analysis_type"
        ] = analysis_type

        parsed[
            "sources_used"
        ] = sources_used

        # ---------------------------------------------------
        # DYNAMIC CONFIDENCE ENGINE
        # ---------------------------------------------------

        expected_fields = 12

        data_fields_present = len([

            value
            for value in stock_data.values()
            if value not in [

                None,
                "",
                "N/A"
            ]
        ])

        confidence_result = (

            self.confidence_engine
            .calculate_confidence(

                retrieval_success_count=(
                    1
                    + len(sources_used)
                ),

                retrieval_total_count=(
                    1
                    + max(
                        len(sources_used),
                        1
                    )
                ),

                resolved_entities=1,

                requested_entities=1,

                data_fields_present=
                data_fields_present,

                expected_data_fields=
                expected_fields,

                llm_parse_success=
                llm_parse_success,

                schema_validation_success=
                schema_validation_success,

                trusted_sources_count=(
                    1
                    + len(sources_used)
                ),

                total_sources_count=(
                    1
                    + max(
                        len(sources_used),
                        1
                    )
                ),

                query_complexity=(

                    self.confidence_engine
                    .detect_query_complexity(

                        companies=
                        [company_name]
                    )
                ),

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
                FundamentalResponse(
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
                f"Schema validation failed: {str(e)}"
            }
