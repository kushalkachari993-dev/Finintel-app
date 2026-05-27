import re

from backend.schemas.query_intelligence_schema import (
    QueryIntelligenceSchema
)
from backend.tools.symbol_registry import SymbolRegistry


class QueryIntelligence:

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        self.symbol_registry = SymbolRegistry()

        self.sector_map = {

            "bank":
            "BANKING",

            "banks":
            "BANKING",

            "banking":
            "BANKING",

            "private bank":
            "BANKING",

            "private banks":
            "BANKING",

            "psu bank":
            "BANKING",

            "psu banks":
            "BANKING",

            "it":
            "IT",

            "technology":
            "IT",

            "tech":
            "IT",

            "software":
            "IT",

            "pharma":
            "PHARMA",

            "healthcare":
            "PHARMA",

            "fmcg":
            "FMCG",

            "auto":
            "AUTOMOBILE",

            "automobile":
            "AUTOMOBILE",

            "energy":
            "ENERGY",

            "oil":
            "ENERGY",

            "gas":
            "ENERGY",

            "metal":
            "METALS",

            "metals":
            "METALS",

            "steel":
            "METALS",

            "real estate":
            "REAL_ESTATE",

            "infra":
            "INFRASTRUCTURE",

            "infrastructure":
            "INFRASTRUCTURE",

            "psu":
            "PSU"
        }

    # ---------------------------------------------------
    # MAIN EXTRACTION
    # ---------------------------------------------------

    def extract(
        self,
        query: str
    ):

        query_lower = query.lower()

        intelligence = {

            "intent":
            self.detect_intent(
                query_lower
            ),

            "sector":
            self.detect_sector(
                query_lower
            ),

            "companies":
            self.extract_companies(
                query,
                intent=self.detect_intent(
                    query_lower
                )
            ),

            "investment_style":
            self.detect_investment_style(
                query_lower
            ),

            "risk_profile":
            self.detect_risk_profile(
                query_lower
            ),

            "analysis_focus":
            self.detect_analysis_focus(
                query_lower
            ),

            "time_horizon":
            self.detect_time_horizon(
                query_lower
            ),

            "geography":
            self.detect_geography(
                query_lower
            ),

            "scope":
            self.detect_scope(
                query_lower
            )
        }

        validated = (
            QueryIntelligenceSchema(
                **intelligence
            )
        )

        return validated.model_dump()

    # ---------------------------------------------------
    # INTENT
    # ---------------------------------------------------

    def detect_intent(
        self,
        query: str
    ):

        # ---------------------------------------------------
        # DISCOVERY STYLE QUERIES
        # ---------------------------------------------------

        if (

            any(
                word in query
                for word in [

                    "top",
                    "best",
                    "leading",
                    "undervalued",
                    "strong",
                    "fundamentally strong",
                    "growth stocks",
                    "value stocks"
                ]
            )

            and

            any(
                word in query
                for word in [

                    "stocks",
                    "companies",
                    "sector",
                    "industry",
                    "banks"
                ]
            )
        ):

            return "DISCOVERY"

        # ---------------------------------------------------
        # COMPARISON
        # ---------------------------------------------------

        if any(
            word in query
            for word in [

                "compare",
                "vs",
                "versus",
                "better than",
                "which is better"
            ]
        ):

            return "COMPARISON"

        # ---------------------------------------------------
        # PRICE QUERY
        # ---------------------------------------------------

        if any(
            word in query
            for word in [

                "price",
                "trading at",
                "share price",
                "stock price",
                "market price"
            ]
        ):

            return "PRICE_QUERY"

        # ---------------------------------------------------
        # DISCOVERY
        # ---------------------------------------------------

        if any(
            word in query
            for word in [

                "top",
                "best",
                "leading"
            ]
        ):

            return "DISCOVERY"

        # ---------------------------------------------------
        # NEWS
        # ---------------------------------------------------

        if any(
            word in query
            for word in [

                "news",
                "latest",
                "updates",
                "recent",
                "happened",
                "announcement",
                "announcements"
            ]
        ):

            return "NEWS"

        # ---------------------------------------------------
        # EDUCATIONAL
        # ---------------------------------------------------

        if any(
            word in query
            for word in [

                "what is",
                "explain",
                "meaning",
                "define",
                "mean"
            ]
        ):

            return "EDUCATIONAL"

        return "FUNDAMENTAL"

    # ---------------------------------------------------
    # SECTOR
    # ---------------------------------------------------

    def detect_sector(
        self,
        query: str
    ):

        for keyword, sector in (
            self.sector_map.items()
        ):

            if keyword in query:

                return sector

        return None

    # ---------------------------------------------------
    # COMPANIES
    # ---------------------------------------------------

    def extract_companies(
        self,
        query: str,
        intent: str = None
    ):

        query_lower = query.lower()

        companies = []

        companies.extend(
            self.symbol_registry.extract_company_names(query)
        )

        # ---------------------------------------------------
        # REMOVE DUPLICATES
        # ---------------------------------------------------

        companies = list(
            dict.fromkeys(companies)
        )

        # ---------------------------------------------------
        # FALLBACK NLP EXTRACTION
        # ---------------------------------------------------

        if companies:

            return companies

        if intent == "EDUCATIONAL":

            return []

        query_clean = (

            query.replace(",", " ")
            .replace("?", " ")
            .replace(".", " ")
        )

        words = query_clean.split()

        blocked_words = {

            "compare",
            "what",
            "which",
            "is",
            "are",
            "the",
            "latest",
            "recent",
            "today",
            "rbi",
            "does",
            "do",
            "explain",
            "meaning",
            "define",
            "definition",
            "top",
            "best",
            "stocks",
            "stock",
            "companies",
            "company",
            "sector",
            "industry",
            "growth",
            "value",
            "undervalued",
            "overvalued",
            "safe",
            "risk",
            "long",
            "term",
            "short",
            "investment",
            "investments",
            "banking",
            "banks",
            "technology",
            "tech",
            "it",
            "market",
            "indian",
            "india",
            "future",
            "strong",
            "fundamentally",
            "financially",
            "buy",
            "sell",
            "hold"
        }

        financial_terms = {

            "roe",
            "roce",
            "pe",
            "p/e",
            "pb",
            "p/b",
            "eps",
            "ebitda",
            "cagr",
            "dividend",
            "yield",
            "ratio",
            "ratios",
            "valuation",
            "profitability",
            "margin",
            "margins",
            "debt",
            "equity"
        }

        blocked_words.update(
            financial_terms
        )

        candidates = []

        for word in words:

            cleaned = word.strip()

            if not cleaned:

                continue

            if cleaned.lower() in blocked_words:

                continue

            if (

                cleaned[0].isupper()

                or cleaned.isupper()
            ):

                if len(cleaned) >= 3:

                    candidates.append(
                        cleaned
                    )

        candidates = list(
            dict.fromkeys(candidates)
        )

        return candidates

    # ---------------------------------------------------
    # INVESTMENT STYLE
    # ---------------------------------------------------

    def detect_investment_style(
        self,
        query: str
    ):

        styles = []

        if any(
            word in query
            for word in [

                "undervalued",
                "cheap",
                "value"
            ]
        ):

            styles.append(
                "VALUE"
            )

        if any(
            word in query
            for word in [

                "growth",
                "future"
            ]
        ):

            styles.append(
                "GROWTH"
            )

        if any(
            word in query
            for word in [

                "dividend",
                "income"
            ]
        ):

            styles.append(
                "DIVIDEND"
            )

        if any(
            word in query
            for word in [

                "quality",
                "strong fundamentals",
                "fundamentally strong"
            ]
        ):

            styles.append(
                "QUALITY"
            )

        return styles

    # ---------------------------------------------------
    # RISK PROFILE
    # ---------------------------------------------------

    def detect_risk_profile(
        self,
        query: str
    ):

        if any(
            word in query
            for word in [

                "safe",
                "low risk",
                "stable"
            ]
        ):

            return "LOW_RISK"

        if any(
            word in query
            for word in [

                "aggressive",
                "high risk",
                "volatile"
            ]
        ):

            return "HIGH_RISK"

        return None

    # ---------------------------------------------------
    # ANALYSIS FOCUS
    # ---------------------------------------------------

    def detect_analysis_focus(
        self,
        query: str
    ):

        focus = []

        mapping = {

            "VALUATION": [

                "valuation",
                "pe",
                "pb",
                "undervalued"
            ],

            "PROFITABILITY": [

                "roe",
                "roce",
                "margin",
                "profitability"
            ],

            "DEBT": [

                "debt",
                "borrowings",
                "leverage"
            ],

            "DIVIDEND": [

                "dividend",
                "yield"
            ],

            "GROWTH": [

                "growth",
                "expansion"
            ],

            "RISK": [

                "risk",
                "safe",
                "volatile"
            ]
        }

        for category, keywords in (
            mapping.items()
        ):

            if any(
                word in query
                for word in keywords
            ):

                focus.append(
                    category
                )

        return focus

    # ---------------------------------------------------
    # TIME HORIZON
    # ---------------------------------------------------

    def detect_time_horizon(
        self,
        query: str
    ):

        if any(
            word in query
            for word in [

                "long term",
                "5 years",
                "10 years"
            ]
        ):

            return "LONG_TERM"

        if any(
            word in query
            for word in [

                "short term",
                "swing",
                "intraday"
            ]
        ):

            return "SHORT_TERM"

        return None

    # ---------------------------------------------------
    # GEOGRAPHY
    # ---------------------------------------------------

    def detect_geography(
        self,
        query: str
    ):

        if "us" in query:

            return "US"

        if "india" in query:

            return "INDIA"

        if "global" in query:

            return "GLOBAL"

        return "INDIA"

    # ---------------------------------------------------
    # SCOPE
    # ---------------------------------------------------

    def detect_scope(
        self,
        query: str
    ):

        if any(
            word in query
            for word in [

                "economy",
                "macro",
                "inflation",
                "gdp"
            ]
        ):

            return "MACRO"

        if any(
            word in query
            for word in [

                "sector",
                "industry"
            ]
        ):

            return "SECTOR"

        return "COMPANY"
