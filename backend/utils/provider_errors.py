import logging


logger = logging.getLogger(__name__)


PROVIDER_TEMPORARY_ERROR = (
    "AI provider is temporarily unavailable. Please try again later."
)

PROVIDER_QUOTA_ERROR = (
    "AI provider quota is temporarily unavailable. Please try again after the daily limit refreshes."
)


def is_provider_quota_error(
    error: Exception | str
) -> bool:
    message = str(
        error
    ).lower()

    return any(
        marker in message
        for marker in [
            "rate_limit_exceeded",
            "rate limit reached",
            "tokens per day",
            "tpm",
            "tpd",
            "quota"
        ]
    )


def is_provider_error_text(
    value: str
) -> bool:
    lowered = (
        value or ""
    ).lower()

    return any(
        marker in lowered
        for marker in [
            "error code:",
            "rate_limit_exceeded",
            "rate limit reached",
            "tokens per day",
            "invalid api key",
            "authentication",
            "service unavailable"
        ]
    )


def safe_provider_error(
    error: Exception | str,
    context: str
) -> str:
    logger.warning(
        "provider_error context=%s error=%s",
        context,
        str(error)
    )

    if is_provider_quota_error(
        error
    ):
        return PROVIDER_QUOTA_ERROR

    return PROVIDER_TEMPORARY_ERROR
