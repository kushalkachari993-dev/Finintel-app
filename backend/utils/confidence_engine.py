from typing import List
from typing import Optional


class ConfidenceEngine:

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        # -----------------------------------------------
        # WEIGHT CONFIGURATION
        # -----------------------------------------------

        self.weights = {

            "retrieval_quality":
            0.30,

            "entity_resolution":
            0.20,

            "data_completeness":
            0.20,

            "llm_output_quality":
            0.15,

            "source_quality":
            0.10,

            "query_complexity":
            0.05
        }

    # ---------------------------------------------------
    # MAIN CONFIDENCE CALCULATOR
    # ---------------------------------------------------

    def calculate_confidence(

        self,

        retrieval_success_count: int = 0,

        retrieval_total_count: int = 0,

        resolved_entities: int = 0,

        requested_entities: int = 0,

        data_fields_present: int = 0,

        expected_data_fields: int = 0,

        llm_parse_success: bool = True,

        schema_validation_success: bool = True,

        trusted_sources_count: int = 0,

        total_sources_count: int = 0,

        query_complexity: str = "MEDIUM",

        ambiguity_detected: bool = False,

        api_failures: int = 0
    ):

        # -----------------------------------------------
        # RETRIEVAL QUALITY
        # -----------------------------------------------

        retrieval_score = self.compute_ratio(

            retrieval_success_count,
            retrieval_total_count
        )

        # -----------------------------------------------
        # ENTITY RESOLUTION QUALITY
        # -----------------------------------------------

        entity_score = self.compute_ratio(

            resolved_entities,
            requested_entities
        )

        # -----------------------------------------------
        # DATA COMPLETENESS
        # -----------------------------------------------

        completeness_score = self.compute_ratio(

            data_fields_present,
            expected_data_fields
        )

        # -----------------------------------------------
        # LLM QUALITY
        # -----------------------------------------------

        llm_score = self.compute_llm_score(

            llm_parse_success,
            schema_validation_success
        )

        # -----------------------------------------------
        # SOURCE QUALITY
        # -----------------------------------------------

        source_score = self.compute_ratio(

            trusted_sources_count,
            total_sources_count
        )

        # -----------------------------------------------
        # QUERY COMPLEXITY
        # -----------------------------------------------

        complexity_score = self.compute_complexity_score(

            query_complexity,
            ambiguity_detected
        )

        # -----------------------------------------------
        # WEIGHTED CONFIDENCE
        # -----------------------------------------------

        confidence = (

            retrieval_score
            * self.weights["retrieval_quality"]

            +

            entity_score
            * self.weights["entity_resolution"]

            +

            completeness_score
            * self.weights["data_completeness"]

            +

            llm_score
            * self.weights["llm_output_quality"]

            +

            source_score
            * self.weights["source_quality"]

            +

            complexity_score
            * self.weights["query_complexity"]
        )

        # -----------------------------------------------
        # API FAILURE PENALTY
        # -----------------------------------------------

        confidence -= (

            api_failures * 0.12
        )

        # -----------------------------------------------
        # CLAMP
        # -----------------------------------------------

        confidence = max(
            0.0,
            min(
                confidence,
                1.0
            )
        )

        # -----------------------------------------------
        # ROUND
        # -----------------------------------------------

        confidence = round(
            confidence,
            2
        )

        # -----------------------------------------------
        # FACTORS
        # -----------------------------------------------

        factors = self.generate_factors(

            retrieval_score=
            retrieval_score,

            entity_score=
            entity_score,

            completeness_score=
            completeness_score,

            llm_score=
            llm_score,

            source_score=
            source_score,

            complexity_score=
            complexity_score,

            ambiguity_detected=
            ambiguity_detected,

            api_failures=
            api_failures
        )

        # -----------------------------------------------
        # RETURN STRUCTURED RESULT
        # -----------------------------------------------

        return {

            "confidence_score":
            confidence,

            "confidence_level":
            self.get_confidence_level(
                confidence
            ),

            "breakdown": {

                "retrieval_score":
                round(retrieval_score, 2),

                "entity_score":
                round(entity_score, 2),

                "completeness_score":
                round(completeness_score, 2),

                "llm_score":
                round(llm_score, 2),

                "source_score":
                round(source_score, 2),

                "complexity_score":
                round(complexity_score, 2)
            },

            "factors":
            factors
        }

    # ---------------------------------------------------
    # SAFE RATIO
    # ---------------------------------------------------

    def compute_ratio(

        self,
        numerator: int,
        denominator: int
    ):

        # -----------------------------------------------
        # NOT APPLICABLE
        # -----------------------------------------------

        if denominator <= 0:

            return 1.0

        return min(
            numerator / denominator,
            1.0
        )

    # ---------------------------------------------------
    # LLM QUALITY SCORE
    # ---------------------------------------------------

    def compute_llm_score(

        self,

        llm_parse_success: bool,

        schema_validation_success: bool
    ):

        score = 1.0

        if not llm_parse_success:

            score -= 0.5

        if not schema_validation_success:

            score -= 0.3

        return max(
            score,
            0.0
        )

    # ---------------------------------------------------
    # COMPLEXITY SCORE
    # ---------------------------------------------------

    def compute_complexity_score(

        self,

        complexity: str,

        ambiguity_detected: bool
    ):

        complexity = complexity.upper()

        if complexity == "LOW":

            score = 1.0

        elif complexity == "MEDIUM":

            score = 0.8

        elif complexity == "HIGH":

            score = 0.6

        else:

            score = 0.5

        # -----------------------------------------------
        # AMBIGUITY PENALTY
        # -----------------------------------------------

        if ambiguity_detected:

            score -= 0.2

        return max(
            score,
            0.0
        )

    # ---------------------------------------------------
    # CONFIDENCE LEVEL
    # ---------------------------------------------------

    def get_confidence_level(
        self,
        score: float
    ):

        if score >= 0.85:

            return "VERY_HIGH"

        elif score >= 0.70:

            return "HIGH"

        elif score >= 0.50:

            return "MEDIUM"

        return "LOW"

    # ---------------------------------------------------
    # FACTOR GENERATION
    # ---------------------------------------------------

    def generate_factors(

        self,

        retrieval_score: float,

        entity_score: float,

        completeness_score: float,

        llm_score: float,

        source_score: float,

        complexity_score: float,

        ambiguity_detected: bool,

        api_failures: int
    ):

        factors = []

        # -----------------------------------------------
        # RETRIEVAL
        # -----------------------------------------------

        if retrieval_score >= 0.8:

            factors.append(
                "Strong retrieval quality detected."
            )

        elif retrieval_score < 0.5:

            factors.append(
                "Retrieval quality was weak."
            )

        # -----------------------------------------------
        # ENTITY RESOLUTION
        # -----------------------------------------------

        if entity_score >= 0.8:

            factors.append(
                "Entity resolution succeeded reliably."
            )

        elif entity_score < 0.5:

            factors.append(
                "Some entities could not be resolved."
            )

        # -----------------------------------------------
        # DATA COMPLETENESS
        # -----------------------------------------------

        if completeness_score >= 0.8:

            factors.append(
                "Financial data completeness was high."
            )

        elif completeness_score < 0.5:

            factors.append(
                "Financial data completeness was limited."
            )

        # -----------------------------------------------
        # LLM QUALITY
        # -----------------------------------------------

        if llm_score >= 0.9:

            factors.append(
                "LLM output passed parsing and validation."
            )

        else:

            factors.append(
                "LLM output quality issues detected."
            )

        # -----------------------------------------------
        # SOURCE QUALITY
        # -----------------------------------------------

        if source_score >= 0.8:

            factors.append(
                "Trusted sources were successfully used."
            )

        elif source_score < 0.5:

            factors.append(
                "Limited trusted-source coverage."
            )

        # -----------------------------------------------
        # COMPLEXITY
        # -----------------------------------------------

        if complexity_score < 0.6:

            factors.append(
                "Query complexity reduced confidence."
            )

        # -----------------------------------------------
        # AMBIGUITY
        # -----------------------------------------------

        if ambiguity_detected:

            factors.append(
                "Ambiguous query intent detected."
            )

        # -----------------------------------------------
        # API FAILURES
        # -----------------------------------------------

        if api_failures > 0:

            factors.append(
                f"{api_failures} API failure(s) impacted reliability."
            )

        return factors

    # ---------------------------------------------------
    # DETECT QUERY COMPLEXITY
    # ---------------------------------------------------

    def detect_query_complexity(

        self,

        companies: Optional[List[str]] = None,

        has_news: bool = False,

        has_comparison: bool = False,

        has_discovery: bool = False,

        has_macro: bool = False
    ):

        companies = companies or []

        score = 0

        # -----------------------------------------------
        # MULTI COMPANY
        # -----------------------------------------------

        if len(companies) >= 3:

            score += 2

        elif len(companies) == 2:

            score += 1

        # -----------------------------------------------
        # QUERY TYPE COMPLEXITY
        # -----------------------------------------------

        if has_news:

            score += 1

        if has_comparison:

            score += 1

        if has_discovery:

            score += 1

        if has_macro:

            score += 2

        # -----------------------------------------------
        # FINAL CLASSIFICATION
        # -----------------------------------------------

        if score <= 1:

            return "LOW"

        elif score <= 3:

            return "MEDIUM"

        return "HIGH"