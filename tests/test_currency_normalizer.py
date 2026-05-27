from backend.tools.financial_normalizer import FinancialNormalizer


def test_usd_billion_and_million_text_converts_to_inr_terms():
    text = (
        "Revenue was $5.04 billion, net income was $919 million, "
        "and market cap was $50.45 billion."
    )

    converted = FinancialNormalizer.normalize_usd_amounts_in_text(
        text,
        usd_to_inr_rate=83.0
    )

    assert "$" not in converted
    assert "INR 41832.00 Cr" in converted
    assert "INR 7627.70 Cr" in converted
    assert "INR 4.19 Lakh Cr" in converted


def test_usd_text_conversion_handles_nested_payloads():
    payload = {
        "headline_summary": "Revenue was $5.04 billion.",
        "key_events": [
            "Net income was $919 million."
        ]
    }

    converted = FinancialNormalizer.normalize_usd_amounts(
        payload,
        usd_to_inr_rate=83.0
    )

    assert converted["headline_summary"] == (
        "Revenue was INR 41832.00 Cr."
    )
    assert converted["key_events"] == [
        "Net income was INR 7627.70 Cr."
    ]
