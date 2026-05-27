import json
import re

from groq import Groq

from backend.config.settings import (
    GROQ_API_KEY,
    GROQ_MODEL
)

from backend.tools.stock_data_tool import (
    StockDataTool
)

from backend.tools.financial_metrics_interpreter import (
    FinancialMetricsInterpreter
)

from backend.tools.ticker_resolver import (
    TickerResolver
)
from backend.utils.provider_errors import (
    safe_provider_error
)


class GroqProvider:

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

        self.interpreter = (
            FinancialMetricsInterpreter()
        )

        self.ticker_resolver = (
            TickerResolver()
        )

    # ---------------------------------------------------
    # RAW GENERATION
    # ---------------------------------------------------

    def generate_raw(
        self,
        prompt: str,
        temperature: float = 0,
        max_tokens: int = 1000,
        system_prompt: str = (
            "You are a financial AI assistant."
        ),
        model: str | None = None
    ):

        try:

            response = (

                self.client
                .chat.completions.create(

                    model=
                    model or GROQ_MODEL,

                    messages=[

                        {
                            "role": "system",

                            "content":
                            system_prompt
                        },

                        {
                            "role": "user",

                            "content":
                            prompt
                        }
                    ],

                    temperature=temperature,

                    max_tokens=max_tokens
                )
            )

            return (

                response
                .choices[0]
                .message.content
                .strip()
            )

        except Exception as e:

            return safe_provider_error(
                e,
                "groq_generate_raw"
            )

    # ---------------------------------------------------
    # DETECT ANALYSIS TYPE
    # ---------------------------------------------------

    def detect_analysis_type(
        self,
        query: str
    ):

        query = query.lower()

        # -----------------------------------
        # VALUATION
        # -----------------------------------

        if any(
            word in query
            for word in [

                "valuation",
                "overvalued",
                "undervalued",
                "expensive",
                "cheap",
                "pe ratio",
                "pb ratio"
            ]
        ):

            return "VALUATION"

        # -----------------------------------
        # RISK
        # -----------------------------------

        elif any(
            word in query
            for word in [

                "risk",
                "safe",
                "danger",
                "debt",
                "crash"
            ]
        ):

            return "RISK"

        # -----------------------------------
        # GROWTH
        # -----------------------------------

        elif any(
            word in query
            for word in [

                "growth",
                "future",
                "expansion",
                "long term"
            ]
        ):

            return "GROWTH"

        # -----------------------------------
        # DIVIDEND
        # -----------------------------------

        elif any(
            word in query
            for word in [

                "dividend",
                "income"
            ]
        ):

            return "DIVIDEND"

        # -----------------------------------
        # PROFITABILITY
        # -----------------------------------

        elif any(
            word in query
            for word in [

                "profitability",
                "margin",
                "roe",
                "roce"
            ]
        ):

            return "PROFITABILITY"

        # -----------------------------------
        # GENERAL FUNDAMENTAL
        # -----------------------------------

        else:

            return "FUNDAMENTAL"

    # ---------------------------------------------------
    # MAIN GENERATE
    # ---------------------------------------------------

    def generate(
        self,
        query: str,
        model: str | None = None
    ):

        # -----------------------------------
        # RESOLVE COMPANY
        # -----------------------------------

        resolved = (

            self.ticker_resolver
            .resolve(query)
        )

        if not resolved:

            return {

                "error":
                "Could not identify stock/company."
            }

        ticker = resolved.get(
            "ticker"
        )

        resolved_company_name = (
            resolved.get(
                "company_name"
            )
        )

        # -----------------------------------
        # FETCH STOCK DATA
        # -----------------------------------

        stock_data = (

            self.stock_tool
            .get_stock_data(
                ticker
            )
        )

        # -----------------------------------
        # CHECK FETCH FAILURE
        # -----------------------------------

        if not stock_data:

            return {

                "error":
                "Failed to fetch stock data."
            }

        if "error" in stock_data:

            return stock_data

        # -----------------------------------
        # INTERPRET METRICS
        # -----------------------------------

        interpretations = (

            self.interpreter
            .generate_interpretation(
                stock_data
            )
        )

        # -----------------------------------
        # DETECT ANALYSIS TYPE
        # -----------------------------------

        analysis_type = (

            self.detect_analysis_type(
                query
            )
        )

        # -----------------------------------
        # SYSTEM PROMPT
        # -----------------------------------

        system_prompt = """
You are an advanced financial AI assistant.

IMPORTANT RULES:

- Use the provided interpretations.
- Do NOT independently reinterpret financial ratios.
- Do NOT invent additional financial conclusions.
- Do NOT hallucinate.
- Maintain balanced reasoning.
- Mention both positives and risks.
- Avoid hype/speculation.
- Avoid guaranteed returns.
- Maintain professional tone.
- Keep explanations concise but insightful.
- Return ONLY valid JSON.
"""

        # -----------------------------------
        # USER PROMPT
        # -----------------------------------

        user_prompt = f"""
USER QUERY:
{query}

RESOLVED COMPANY:
{resolved_company_name}

TICKER:
{ticker}

ANALYSIS TYPE:
{analysis_type}

RAW STOCK DATA:
{json.dumps(stock_data, indent=2)}

PRE-COMPUTED INTERPRETATIONS:
{json.dumps(interpretations, indent=2)}

IMPORTANT:

- Use the provided interpretations directly.
- Do NOT reinterpret metrics independently.
- Do NOT create new financial conclusions.
- Do NOT contradict interpretations.
- Use balanced financial reasoning.

Return ONLY valid JSON:

{{
    "company_name": "",

    "ticker": "",

    "analysis_type": "",

    "business_overview": "",

    "financial_strengths": [
        "",
        ""
    ],

    "financial_risks": [
        "",
        ""
    ],

    "valuation_commentary": "",

    "overall_view": "",

    "confidence_score": 0.0,

    "disclaimer": ""
}}
"""

        # -----------------------------------
        # GROQ CALL
        # -----------------------------------

        response = (

            self.client
            .chat.completions.create(

                model=
                model or GROQ_MODEL,

                messages=[

                    {
                        "role": "system",

                        "content":
                        system_prompt
                    },

                    {
                        "role": "user",

                        "content":
                        user_prompt
                    }
                ],

                temperature=0.2,

                max_tokens=1000
            )
        )

        raw_output = (

            response
            .choices[0]
            .message.content
            .strip()
        )

        # -----------------------------------
        # CLEAN MARKDOWN
        # -----------------------------------

        raw_output = re.sub(
            r"```json|```",
            "",
            raw_output
        ).strip()

        # -----------------------------------
        # PARSE JSON
        # -----------------------------------

        try:

            parsed = json.loads(
                raw_output
            )

            # -----------------------------------
            # FORCE CONSISTENCY
            # -----------------------------------

            parsed["ticker"] = ticker

            if not parsed.get(
                "company_name"
            ):

                parsed[
                    "company_name"
                ] = (
                    resolved_company_name
                )

            if not parsed.get(
                "analysis_type"
            ):

                parsed[
                    "analysis_type"
                ] = analysis_type

            return parsed

        except Exception:

            return {

                "error":
                "Failed to parse model response.",

                "raw_output":
                raw_output
            }
