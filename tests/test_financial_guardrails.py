from backend.utils.financial_guardrails import (
    apply_financial_guardrails
)


def test_guardrails_convert_direct_recommendation_field():

    response = {
        "success": True,
        "data": {
            "company_name": "TCS",
            "recommendation": "Buy",
            "summary": "TCS looks attractive.",
            "sources_used": [
                "https://example.com/tcs"
            ],
            "disclaimer": "Educational only."
        },
        "error": None
    }

    guarded = apply_financial_guardrails(
        response,
        "FUNDAMENTAL"
    )

    assert guarded["data"]["recommendation"].startswith(
        "Positive research view"
    )
    assert guarded["data"]["guardrails"]["applied"] is True
    assert any(
        "converted"
        in warning
        for warning in guarded["data"]["guardrails"]["warnings"]
    )
    assert "not investment advice" in guarded["data"]["disclaimer"].lower()


def test_guardrails_normalize_short_usd_amounts_in_text():

    response = {
        "success": True,
        "data": {
            "company_name": "TCS",
            "stock_overview": "Market cap is $8.53T in this source.",
            "sources_used": [
                "https://example.com/tcs"
            ],
            "disclaimer": "Educational only and not investment advice."
        },
        "error": None
    }

    guarded = apply_financial_guardrails(
        response,
        "REPORT"
    )

    assert "$8.53T" not in guarded["data"]["stock_overview"]
    assert "INR" in guarded["data"]["stock_overview"]
    assert any(
        "normalized"
        in warning
        for warning in guarded["data"]["guardrails"]["warnings"]
    )


def test_guardrails_flag_missing_sources_for_source_backed_routes():

    response = {
        "success": True,
        "data": {
            "summary": "A source-backed claim without sources.",
            "disclaimer": "Educational only and not investment advice."
        },
        "error": None
    }

    guarded = apply_financial_guardrails(
        response,
        "NEWS"
    )

    assert guarded["data"]["guardrails"]["source_quality"]["label"] == "Missing"
    assert any(
        "No external source"
        in warning
        for warning in guarded["data"]["guardrails"]["warnings"]
    )
