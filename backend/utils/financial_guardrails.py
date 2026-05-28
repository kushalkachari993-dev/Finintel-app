import copy
import re
from datetime import datetime
from datetime import timezone
from typing import Any

from backend.config import settings
from backend.tools.financial_normalizer import FinancialNormalizer


SOURCE_FIELDS = (
    "sources_used",
    "sources"
)

ADVICE_FIELD_MAP = {
    "buy": "Positive research view; validate valuation, risks, and suitability before acting.",
    "strong buy": "Positive research view; validate valuation, risks, and suitability before acting.",
    "sell": "Cautious research view; validate fundamentals, valuation, and risk before acting.",
    "strong sell": "Cautious research view; validate fundamentals, valuation, and risk before acting.",
    "hold": "Neutral research view; monitor fundamentals, valuation, and risk before acting."
}

DIRECT_ADVICE_PATTERNS = [
    re.compile(
        r"\b(you should|must|definitely)\s+(buy|sell|hold)\b",
        re.IGNORECASE
    ),
    re.compile(
        r"\bguaranteed\s+(return|profit|upside)\b",
        re.IGNORECASE
    ),
    re.compile(
        r"\brisk[- ]free\b",
        re.IGNORECASE
    )
]

USD_SHORT_AMOUNT_PATTERN = re.compile(
    r"\$(\d+(?:\.\d+)?)\s*([MBT])\b",
    re.IGNORECASE
)


def normalize_short_usd_amounts(
    text: str
) -> str:

    def replace(match):

        amount = float(
            match.group(1)
        )
        suffix = match.group(2).upper()
        unit = {
            "M": "million",
            "B": "billion",
            "T": "trillion"
        }[suffix]

        return FinancialNormalizer.usd_amount_to_inr_text(
            amount=amount,
            unit=unit,
            usd_to_inr_rate=settings.USD_TO_INR_RATE
        )

    return USD_SHORT_AMOUNT_PATTERN.sub(
        replace,
        text
    )


def source_list(
    data: dict
) -> list[str]:

    sources = []

    for field in SOURCE_FIELDS:
        value = data.get(
            field
        )

        if isinstance(
            value,
            list
        ):
            sources.extend(
                str(item)
                for item in value
                if item
            )

    for company in data.get(
        "companies",
        []
    ):
        if isinstance(
            company,
            dict
        ):
            value = company.get(
                "sources",
                []
            )

            if isinstance(
                value,
                list
            ):
                sources.extend(
                    str(item)
                    for item in value
                    if item
                )

    return list(
        dict.fromkeys(
            sources
        )
    )


def data_quality_from_payload(
    data: dict
) -> dict[str, Any]:

    scores = []

    def collect(value):

        if isinstance(
            value,
            dict
        ):
            score = value.get(
                "data_quality_score"
            )

            if isinstance(
                score,
                (int, float)
            ):
                scores.append(
                    float(score)
                )

            for item in value.values():
                collect(
                    item
                )

        elif isinstance(
            value,
            list
        ):
            for item in value:
                collect(
                    item
                )

    collect(
        data
    )

    if not scores:
        return {
            "score": None,
            "label": "Not available"
        }

    average = round(
        sum(scores) / len(scores),
        2
    )

    if average >= 0.8:
        label = "High"
    elif average >= 0.55:
        label = "Medium"
    else:
        label = "Low"

    return {
        "score": average,
        "label": label
    }


def sanitize_advice_field(
    key: str,
    value: Any,
    warnings: list[str]
) -> Any:

    if not isinstance(
        value,
        str
    ):
        return value

    normalized_key = key.lower()
    normalized_value = value.strip().lower()

    if normalized_key in {
        "recommendation",
        "final_recommendation",
        "final_recommendation_label"
    } and normalized_value in ADVICE_FIELD_MAP:
        warnings.append(
            "Direct buy/sell/hold recommendation was converted to a safer research view."
        )

        return ADVICE_FIELD_MAP[
            normalized_value
        ]

    return value


def sanitize_text(
    text: str,
    warnings: list[str]
) -> str:

    original = text
    text = FinancialNormalizer.normalize_usd_amounts_in_text(
        text,
        settings.USD_TO_INR_RATE
    )
    text = normalize_short_usd_amounts(
        text
    )

    if text != original:
        warnings.append(
            "USD-denominated amounts were normalized to INR terms where detected."
        )

    for pattern in DIRECT_ADVICE_PATTERNS:
        if pattern.search(
            text
        ):
            warnings.append(
                "Potentially unsafe financial advice language was detected."
            )

    return text


def sanitize_payload(
    value: Any,
    warnings: list[str],
    key: str = ""
) -> Any:

    if isinstance(
        value,
        dict
    ):
        return {
            item_key: sanitize_payload(
                sanitize_advice_field(
                    item_key,
                    item_value,
                    warnings
                ),
                warnings,
                item_key
            )
            for item_key, item_value in value.items()
        }

    if isinstance(
        value,
        list
    ):
        return [
            sanitize_payload(
                item,
                warnings,
                key
            )
            for item in value
        ]

    if isinstance(
        value,
        str
    ):
        return sanitize_text(
            value,
            warnings
        )

    return value


def source_quality(
    route: str,
    sources: list[str]
) -> dict[str, Any]:

    count = len(
        sources
    )
    source_required = route in {
        "FUNDAMENTAL",
        "COMPARISON",
        "NEWS",
        "DISCOVERY",
        "REPORT"
    }

    if count >= 5:
        label = "Strong"
    elif count >= 2:
        label = "Moderate"
    elif count == 1:
        label = "Light"
    else:
        label = "Missing" if source_required else "Not required"

    return {
        "source_count": count,
        "label": label,
        "requires_sources": source_required
    }


def apply_financial_guardrails(
    response: dict,
    route: str
) -> dict:

    if not isinstance(
        response,
        dict
    ) or response.get("success") is not True:
        return response

    data = response.get(
        "data"
    )

    if not isinstance(
        data,
        dict
    ):
        return response

    guarded_response = copy.deepcopy(
        response
    )
    warnings = []
    sanitized_data = sanitize_payload(
        guarded_response["data"],
        warnings
    )
    sources = source_list(
        sanitized_data
    )
    source_quality_result = source_quality(
        route,
        sources
    )

    if (
        source_quality_result["requires_sources"]
        and source_quality_result["source_count"] == 0
    ):
        warnings.append(
            "No external source links were attached to this financial response."
        )

    sanitized_data["guardrails"] = {
        "applied": True,
        "warnings": list(
            dict.fromkeys(
                warnings
            )
        ),
        "source_quality": source_quality_result,
        "data_quality": data_quality_from_payload(
            sanitized_data
        ),
        "checked_at": datetime.now(
            timezone.utc
        ).isoformat()
    }

    disclaimer = str(
        sanitized_data.get(
            "disclaimer",
            ""
        )
    )

    if "not investment advice" not in disclaimer.lower():
        sanitized_data["disclaimer"] = (
            f"{disclaimer} "
            "This is for educational purposes only and not investment advice."
        ).strip()

    guarded_response["data"] = sanitized_data

    return guarded_response
