import json

from groq import Groq

from backend.config.settings import (
    GROQ_API_KEY,
    GROQ_MODEL
)

from backend.schemas.router_schema import (
    RouterResponse
)


class RouterAgent:

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        self.client = Groq(
            api_key=GROQ_API_KEY
        )

    # ---------------------------------------------------
    # STANDARD RESPONSE
    # ---------------------------------------------------

    def build_response(
        self,
        route: str,
        confidence: float,
        reasoning: str
    ):

        return RouterResponse(

            route=route,

            confidence=confidence,

            reasoning=reasoning
        ).model_dump()

    # ---------------------------------------------------
    # ROUTE SCORING ENGINE
    # ---------------------------------------------------

    def initialize_scores(self):

        return {

            "FUNDAMENTAL": 0,

            "PRICE_QUERY": 0,

            "COMPARISON": 0,

            "EDUCATIONAL": 0,

            "NEWS": 0,

            "DISCOVERY": 0
        }

    # ---------------------------------------------------
    # ROUTER
    # ---------------------------------------------------

    def route(
        self,
        query: str,
        intelligence: dict = None
    ):

        query_lower = query.lower()

        route_scores = (
            self.initialize_scores()
        )

        reasoning_log = []

        # ---------------------------------------------------
        # QUERY INTELLIGENCE LAYER
        # ---------------------------------------------------

        if intelligence:

            intent = intelligence.get(
                "intent"
            )

            companies = intelligence.get(
                "companies",
                []
            )

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

            secondary_intents = intelligence.get(
                "secondary_intents",
                []
            )

            is_ambiguous = intelligence.get(
                "is_ambiguous",
                False
            )

            # ---------------------------------------------------
            # EXPLICIT COMPANY COMPARISON
            # ---------------------------------------------------

            comparison_requested = any(
                word in query_lower
                for word in [
                    "compare",
                    " vs ",
                    " versus ",
                    "better than",
                    "which is better"
                ]
            )

            if (
                len(companies) >= 2
                and (
                    intent == "COMPARISON"
                    or comparison_requested
                )
            ):

                route_scores[
                    "COMPARISON"
                ] += 50

                reasoning_log.append(
                    "Explicit companies detected."
                )

            # ---------------------------------------------------
            # THEMATIC DISCOVERY
            # ---------------------------------------------------

            if (

                len(companies) < 2

                and not companies

                and (
                    sector
                    or investment_style
                    or analysis_focus
                )
            ):

                route_scores[
                    "DISCOVERY"
                ] += 40

                reasoning_log.append(
                    "Thematic discovery query detected."
                )

            # ---------------------------------------------------
            # INTENT BOOST
            # ---------------------------------------------------

            if intent in route_scores:

                route_scores[
                    intent
                ] += 30

                reasoning_log.append(
                    f"Intent boost applied: {intent}"
                )

            # ---------------------------------------------------
            # SECONDARY INTENTS
            # ---------------------------------------------------

            for secondary in secondary_intents:

                if secondary in route_scores:

                    route_scores[
                        secondary
                    ] += 10

            # ---------------------------------------------------
            # AMBIGUITY PENALTY
            # ---------------------------------------------------

            if is_ambiguous:

                for route in route_scores:

                    route_scores[
                        route
                    ] *= 0.9

                reasoning_log.append(
                    "Ambiguity penalty applied."
                )

        # ---------------------------------------------------
        # RULE-BASED SCORING
        # ---------------------------------------------------

        if (
            intelligence
            and intelligence.get("intent") == "EDUCATIONAL"
        ):

            return self.build_response(

                route="EDUCATIONAL",

                confidence=0.95,

                reasoning=(
                    "Educational intent detected from "
                    "query intelligence."
                )
            )

        keyword_map = {

            "PRICE_QUERY": [

                "stock price",
                "share price",
                "current price",
                "market price",
                "trading at",
                "price of"
            ],

            "COMPARISON": [

                "compare",
                "vs",
                "versus"
            ],

            "DISCOVERY": [

                "top",
                "best",
                "leading",
                "sector",
                "industry",
                "undervalued",
                "growth",
                "strong",
                "companies",
                "stocks"
            ],

            "NEWS": [

                "news",
                "latest",
                "headline",
                "announcement",
                "earnings",
                "results",
                "updates"
            ],

            "EDUCATIONAL": [

                "what is",
                "explain",
                "meaning",
                "learn",
                "how does"
            ],

            "FUNDAMENTAL": [

                "fundamental",
                "valuation",
                "financials",
                "balance sheet",
                "cash flow",
                "profitability",
                "roe",
                "roce"
            ]
        }

        # ---------------------------------------------------
        # APPLY KEYWORD SCORES
        # ---------------------------------------------------

        for route, keywords in (
            keyword_map.items()
        ):

            for keyword in keywords:

                if keyword in query_lower:

                    route_scores[
                        route
                    ] += 8

        # ---------------------------------------------------
        # DISCOVERY + COMPARISON CONFLICT
        # ---------------------------------------------------

        if (

            route_scores["COMPARISON"] > 0

            and route_scores["DISCOVERY"] > 0
        ):

            # Explicit companies -> COMPARISON

            if (

                intelligence
                and len(
                    intelligence.get(
                        "companies",
                        []
                    )
                ) >= 2
            ):

                route_scores[
                    "COMPARISON"
                ] += 25

                route_scores[
                    "DISCOVERY"
                ] -= 10

                reasoning_log.append(

                    "Resolved ambiguity in favor "
                    "of explicit comparison."
                )

            else:

                route_scores[
                    "DISCOVERY"
                ] += 20

                reasoning_log.append(

                    "Resolved ambiguity in favor "
                    "of discovery."
                )

        # ---------------------------------------------------
        # DETERMINE BEST ROUTE
        # ---------------------------------------------------

        best_route = max(

            route_scores,

            key=route_scores.get
        )

        best_score = (
            route_scores[
                best_route
            ]
        )

        # ---------------------------------------------------
        # CONFIDENCE CALCULATION
        # ---------------------------------------------------

        sorted_scores = sorted(

            route_scores.values(),

            reverse=True
        )

        top_score = sorted_scores[0]

        second_score = sorted_scores[1]

        confidence_gap = (
            top_score - second_score
        )

        # ---------------------------------------------------
        # DYNAMIC CONFIDENCE
        # ---------------------------------------------------

        if top_score <= 0:

            confidence = 0.4

        elif confidence_gap >= 40:

            confidence = 0.99

        elif confidence_gap >= 25:

            confidence = 0.95

        elif confidence_gap >= 15:

            confidence = 0.90

        elif confidence_gap >= 8:

            confidence = 0.82

        else:

            confidence = 0.72

        # ---------------------------------------------------
        # LOW CONFIDENCE -> LLM FALLBACK
        # ---------------------------------------------------

        if confidence < 0.75:

            llm_result = (
                self.semantic_route(
                    query=query,
                    intelligence=intelligence
                )
            )

            if llm_result:

                return llm_result

        # ---------------------------------------------------
        # FINAL RESPONSE
        # ---------------------------------------------------

        reasoning = (

            " | ".join(reasoning_log)

            if reasoning_log

            else "Rule-based routing applied."
        )

        return self.build_response(

            route=best_route,

            confidence=round(confidence, 2),

            reasoning=reasoning
        )

    # ---------------------------------------------------
    # SEMANTIC ROUTER
    # ---------------------------------------------------

    def semantic_route(
        self,
        query: str,
        intelligence: dict = None
    ):

        system_prompt = """
You are an intelligent routing agent
for an Indian finance AI system.

Classify the query into EXACTLY ONE route.

AVAILABLE ROUTES:

- FUNDAMENTAL
- PRICE_QUERY
- COMPARISON
- EDUCATIONAL
- NEWS
- DISCOVERY

IMPORTANT:

- Explicit companies -> COMPARISON
- Candidate generation -> DISCOVERY

Return ONLY valid JSON.

{
    "route": "...",
    "confidence": 0.0,
    "reasoning": "..."
}
"""

        user_prompt = f"""
QUERY:
{query}

QUERY INTELLIGENCE:
{json.dumps(intelligence, indent=2)}
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

                    max_tokens=120,
                )
            )

            raw_output = (
                response
                .choices[0]
                .message.content
                .strip()
            )

            if raw_output.startswith("```"):

                raw_output = (

                    raw_output
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

            parsed = json.loads(
                raw_output
            )

            route = parsed.get(
                "route",
                "FUNDAMENTAL"
            )

            confidence = parsed.get(
                "confidence",
                0.7
            )

            reasoning = parsed.get(
                "reasoning",
                "Semantic routing applied."
            )

            valid_routes = [

                "FUNDAMENTAL",
                "PRICE_QUERY",
                "COMPARISON",
                "EDUCATIONAL",
                "NEWS",
                "DISCOVERY"
            ]

            if route not in valid_routes:

                return None

            return self.build_response(

                route=route,

                confidence=confidence,

                reasoning=reasoning
            )

        except Exception:

            return None
