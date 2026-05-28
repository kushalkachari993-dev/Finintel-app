from groq import Groq

from backend.config.settings import (
    GROQ_API_KEY,
    GROQ_MODEL,
    RAG_ENABLED
)

from backend.rag import (
    RAGRetriever
)

from backend.utils.json_parser import (
    JSONParser
)

from backend.schemas.educational_schema import (
    EducationalResponse
)
from backend.agents.detail_guidance import (
    answer_detail_guidance,
    answer_detail_tokens
)
from backend.utils.provider_errors import (
    safe_provider_error
)


class EducationalAgent:

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        self.client = Groq(
            api_key=GROQ_API_KEY
        )

        self.retriever = RAGRetriever()

    # ---------------------------------------------------
    # MAIN EDUCATIONAL METHOD
    # ---------------------------------------------------

    def explain(
        self,
        query: str,
        model: str | None = None,
        answer_detail: str = "brief"
    ):

        rag_results = []
        rag_context = ""

        if RAG_ENABLED:

            rag_results = self.retriever.search(
                query
            )

            rag_context = self.retriever.build_context(
                rag_results
            )

        # ---------------------------------------------------
        # SYSTEM PROMPT
        # ---------------------------------------------------

        system_prompt = """
You are FinIntel AI,
a specialized Indian finance education assistant.

Your role is to explain:

- stock market concepts
- investing concepts
- financial ratios
- valuation metrics
- risk concepts
- Indian market terminology

IMPORTANT RULES:

- Keep explanations clear and structured
- Avoid excessive jargon
- Explain concepts simply
- Mention practical interpretation
- Mention limitations when relevant
- Avoid investment recommendations
- Use balanced educational tone
- Do NOT hallucinate
- Be factually accurate
- Use the provided RAG context when relevant
- Do NOT claim a source was used unless it appears in the RAG context

Return ONLY valid JSON.
Do NOT return markdown.
"""
        detail_guidance = answer_detail_guidance(
            answer_detail
        )

        # ---------------------------------------------------
        # USER PROMPT
        # ---------------------------------------------------

        user_prompt = f"""
Explain this finance concept.

QUERY:
{query}

RAG CONTEXT:
{rag_context if rag_context else "No relevant RAG context retrieved."}

ANSWER DETAIL:
{detail_guidance}

Return ONLY valid JSON
using this schema:

{{
    "topic": "",

    "simple_definition": "",

    "detailed_explanation": "",

    "why_it_matters": "",

    "practical_interpretation": "",

    "limitations": "",

    "example": "",

    "confidence_score": 0.0,

    "disclaimer": "",

    "sources_used": []
}}
"""

        # ---------------------------------------------------
        # GROQ API CALL
        # ---------------------------------------------------

        try:

            response = (
                self.client.chat.completions.create(

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

                    max_tokens=answer_detail_tokens(
                        answer_detail,
                        brief_tokens=1200,
                        detailed_tokens=1900
                    )
                )
            )

        except Exception as e:

            return {

                "success": False,

                "data": None,

                "error":
                safe_provider_error(
                    e,
                    "educational_explain"
                )
            }

        # ---------------------------------------------------
        # RAW OUTPUT
        # ---------------------------------------------------

        raw_output = (

            response.choices[0]
            .message.content
            .strip()
        )

        # ---------------------------------------------------
        # SAFE JSON PARSING
        # ---------------------------------------------------

        parsed_output = (
            JSONParser.parse(
                raw_output
            )
        )

        # ---------------------------------------------------
        # PARSE FAILURE
        # ---------------------------------------------------

        if not parsed_output:

            return {

                "success": False,

                "data": None,

                "error":
                "Failed to parse educational response."
            }

        # ---------------------------------------------------
        # FORCE RAG SOURCE CONSISTENCY
        # ---------------------------------------------------

        parsed_output[
            "sources_used"
        ] = [
            result.get("source")
            for result in rag_results
            if result.get("source")
        ]

        # ---------------------------------------------------
        # SCHEMA VALIDATION
        # ---------------------------------------------------

        try:

            validated = (
                EducationalResponse(
                    **parsed_output
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
