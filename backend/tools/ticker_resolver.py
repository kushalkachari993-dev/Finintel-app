import json
import logging
import re

import yfinance as yf

from groq import Groq

from backend.config.settings import (
    GROQ_API_KEY,
    GROQ_MODEL,
    TICKER_CACHE_SECONDS
)

from backend.utils.simple_cache import build_cache
from backend.tools.symbol_registry import SymbolRegistry


logger = logging.getLogger(__name__)


class TickerResolver:

    cache = build_cache(
        ttl_seconds=TICKER_CACHE_SECONDS,
        namespace="ticker"
    )

    # =====================================================
    # INIT
    # =====================================================

    def __init__(self):

        self.client = Groq(
            api_key=GROQ_API_KEY
        )

        self.symbol_registry = SymbolRegistry()

    # =====================================================
    # SAFE NORMALIZER
    # =====================================================

    def normalize(
        self,
        text
    ):

        if text is None:
            return ""

        return (
            str(text)
            .strip()
            .lower()
        )

    # =====================================================
    # LOCAL EXTRACTION
    # =====================================================

    def local_extract(
        self,
        query: str
    ):

        company = self.symbol_registry.resolve_company(query)
        return company.company_name if company else None

    # =====================================================
    # EXTRACT COMPANY NAME USING LLM
    # =====================================================

    def extract_company_name(
        self,
        query: str
    ):

        # -------------------------------------------------
        # LOCAL FAST PATH
        # -------------------------------------------------

        local_match = self.local_extract(query)

        if local_match:
            return local_match

        # -------------------------------------------------
        # LLM FALLBACK
        # -------------------------------------------------

        system_prompt = """
You are a financial entity extraction engine.

Extract ONLY the primary company name.

RULES:
- Return ONLY valid JSON
- No markdown
- No explanations

FORMAT:
{
    "company_name": ""
}
"""

        user_prompt = f"""
QUERY:
{query}
"""

        try:

            response = (

                self.client.chat.completions.create(

                    model=
                    GROQ_MODEL,

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

                    temperature=0,

                    max_tokens=60
                )
            )

            output = (
                response
                .choices[0]
                .message.content
                .strip()
            )

            output = re.sub(
                r"```json|```",
                "",
                output
            ).strip()

            parsed = json.loads(output)

            company_name = parsed.get(
                "company_name"
            )

            if not company_name:
                return None

            return str(company_name).strip()

        except Exception:

            logger.exception(
                "company_name_extraction_failed query=%r",
                query
            )

            return None

    # =====================================================
    # SEARCH YFINANCE
    # =====================================================

    def search_candidates(
        self,
        company_name: str
    ):

        # -------------------------------------------------
        # SAFETY CHECK
        # -------------------------------------------------

        if not company_name:

            return []

        try:

            search = yf.Search(
                query=str(company_name),
                max_results=10
            )

            quotes = getattr(
                search,
                "quotes",
                []
            )

            if not quotes:
                return []

            return quotes

        except Exception:

            logger.exception(
                "ticker_search_failed company_name=%r",
                company_name
            )

            return []

    # =====================================================
    # SELECT BEST MATCH
    # =====================================================

    def select_best_match(
        self,
        candidates
    ):

        if not candidates:

            return None

        # -------------------------------------------------
        # PRIORITIZE NSE EQUITIES
        # -------------------------------------------------

        for candidate in candidates:

            symbol = candidate.get(
                "symbol",
                ""
            )

            quote_type = candidate.get(
                "quoteType",
                ""
            )

            if (
                symbol
                and symbol.endswith(".NS")
                and quote_type == "EQUITY"
            ):

                return {

                    "ticker":
                    symbol,

                    "company_name":
                    candidate.get(
                        "shortname",
                        symbol
                    ),

                    "exchange":
                    "NSE",

                    "confidence":
                    0.9
                }

        # -------------------------------------------------
        # FALLBACK
        # -------------------------------------------------

        first = candidates[0]

        return {

            "ticker":
            first.get(
                "symbol"
            ),

            "company_name":
            first.get(
                "shortname",
                "UNKNOWN"
            ),

            "exchange":
            first.get(
                "exchange",
                "UNKNOWN"
            ),

            "confidence":
            0.7
        }

    # =====================================================
    # MAIN RESOLVE
    # =====================================================

    def resolve(
        self,
        query: str
    ):

        # -------------------------------------------------
        # SAFETY
        # -------------------------------------------------

        if not query:

            return None

        cache_key = self.normalize(
            query
        )

        cached = self.cache.get(
            cache_key
        )

        if cached is not None:

            logger.info(
                "ticker_cache_hit query=%r",
                query
            )

            return cached

        # -------------------------------------------------
        # EXTRACT COMPANY
        # -------------------------------------------------

        company_name = (

            self.extract_company_name(
                query
            )
        )

        if not company_name:

            return None

        local_company = self.symbol_registry.resolve_company(
            company_name
        )

        if local_company:

            return self.cache.set(
                cache_key,
                self.symbol_registry.to_ticker_result(
                    local_company
                )
            )

        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

        candidates = (

            self.search_candidates(
                company_name
            )
        )

        if not candidates:

            return None

        # -------------------------------------------------
        # BEST MATCH
        # -------------------------------------------------

        best_match = (

            self.select_best_match(
                candidates
            )
        )

        if best_match:

            return self.cache.set(
                cache_key,
                best_match
            )

        return None
