from typing import Any


REQUIRED_FIELDS = {
    "PRICE_QUERY": [
        "company_name",
        "ticker",
        "current_price",
        "confidence_score",
        "disclaimer",
        "message"
    ],
    "EDUCATIONAL": [
        "topic",
        "simple_definition",
        "detailed_explanation",
        "confidence_score",
        "disclaimer",
        "sources_used"
    ],
    "DISCOVERY": [
        "query_type",
        "summary",
        "key_points",
        "mentioned_companies",
        "confidence_score",
        "sources_used"
    ],
    "NEWS": [
        "company_name",
        "ticker",
        "headline_summary",
        "key_events",
        "market_impact",
        "sentiment",
        "risk_factors",
        "confidence_score",
        "disclaimer",
        "sources"
    ],
    "COMPARISON": [
        "comparison_type",
        "companies_compared",
        "comparative_analysis",
        "winner_summary",
        "balanced_view",
        "confidence_score",
        "sources_used",
        "disclaimer"
    ],
    "FUNDAMENTAL": [
        "company_name",
        "ticker",
        "analysis_type",
        "business_overview",
        "financial_strengths",
        "financial_risks",
        "valuation_commentary",
        "overall_view",
        "confidence_score",
        "sources_used",
        "disclaimer"
    ]
}

SAFETY_PHRASES = [
    "guaranteed return",
    "guaranteed profit",
    "sure profit",
    "risk-free return",
    "must buy",
    "will definitely",
    "target price"
]


def has_value(value: Any):

    if value is None:

        return False

    if isinstance(value, str):

        return bool(value.strip())

    if isinstance(value, list):

        return len(value) > 0

    if isinstance(value, dict):

        return len(value) > 0

    return True


def flatten_text(value: Any):

    if isinstance(value, str):

        return value

    if isinstance(value, list):

        return " ".join(
            flatten_text(item)
            for item in value
        )

    if isinstance(value, dict):

        return " ".join(
            flatten_text(item)
            for item in value.values()
        )

    return ""


def evaluate_response(
    route: str,
    response: dict
):

    issues = []

    if not isinstance(response, dict):

        return [
            "Response must be a dictionary."
        ]

    if response.get("success") is not True:

        issues.append(
            "Response success must be true."
        )

    data = response.get("data")

    if not isinstance(data, dict):

        issues.append(
            "Response data must be a dictionary."
        )

        return issues

    required = REQUIRED_FIELDS.get(
        route,
        []
    )

    for field in required:

        if not has_value(
            data.get(field)
        ):

            issues.append(
                f"Missing or empty required field: {field}"
            )

    confidence = data.get(
        "confidence_score"
    )

    if confidence is not None:

        try:

            confidence = float(confidence)

            if confidence < 0 or confidence > 1:

                issues.append(
                    "confidence_score must be between 0 and 1."
                )

        except Exception:

            issues.append(
                "confidence_score must be numeric."
            )

    if route in [
        "EDUCATIONAL",
        "FUNDAMENTAL",
        "COMPARISON",
        "NEWS",
        "DISCOVERY"
    ]:

        source_field = (
            "sources"
            if route == "NEWS"
            else "sources_used"
        )

        sources = data.get(
            source_field,
            []
        )

        if not isinstance(sources, list) or not sources:

            issues.append(
                f"{source_field} must contain at least one source."
            )

    text = flatten_text(data).lower()

    for phrase in SAFETY_PHRASES:

        if phrase in text:

            issues.append(
                f"Unsafe financial phrase detected: {phrase}"
            )

    return issues
