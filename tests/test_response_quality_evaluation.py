import json
from pathlib import Path

from backend.evaluators.response_quality import (
    evaluate_response
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "agent_response_eval_cases.json"
)


def load_cases():

    return json.loads(
        FIXTURE_PATH.read_text(
            encoding="utf-8"
        )
    )


def test_agent_response_eval_cases_pass_quality_checks():

    failures = []

    for case in load_cases():

        issues = evaluate_response(
            route=case["route"],
            response=case["response"]
        )

        if issues:

            failures.append({
                "route": case["route"],
                "issues": issues
            })

    assert failures == []


def test_response_quality_flags_unsafe_financial_language():

    issues = evaluate_response(
        route="FUNDAMENTAL",
        response={
            "success": True,
            "data": {
                "company_name": "Example Co",
                "ticker": "EXAMPLE.NS",
                "analysis_type": "GENERAL",
                "business_overview": "This is a must buy with guaranteed return.",
                "financial_strengths": ["Good margins"],
                "financial_risks": ["Execution risk"],
                "valuation_commentary": "Valuation should be checked.",
                "overall_view": "Balanced view.",
                "confidence_score": 0.9,
                "sources_used": ["https://example.com"],
                "disclaimer": "Educational only."
            },
            "error": None
        }
    )

    assert any(
        "Unsafe financial phrase" in issue
        for issue in issues
    )
