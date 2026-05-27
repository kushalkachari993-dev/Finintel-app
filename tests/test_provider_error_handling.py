from backend.utils.provider_errors import PROVIDER_QUOTA_ERROR
from backend.utils.provider_errors import PROVIDER_TEMPORARY_ERROR
from backend.utils.provider_errors import is_provider_error_text
from backend.utils.provider_errors import safe_provider_error


def test_safe_provider_error_hides_raw_groq_quota_message():
    raw_error = (
        "Error code: 429 - {'error': {'message': "
        "'Rate limit reached for model llama on tokens per day', "
        "'code': 'rate_limit_exceeded'}}"
    )

    message = safe_provider_error(
        raw_error,
        "test"
    )

    assert message == PROVIDER_QUOTA_ERROR
    assert "llama" not in message
    assert "429" not in message
    assert "rate_limit_exceeded" not in message


def test_safe_provider_error_hides_generic_provider_message():
    message = safe_provider_error(
        "Error code: 503 - provider exploded",
        "test"
    )

    assert message == PROVIDER_TEMPORARY_ERROR
    assert "503" not in message


def test_provider_error_text_detection():
    assert is_provider_error_text(
        "Error code: 429 - rate_limit_exceeded"
    )
    assert not is_provider_error_text(
        '{"summary": "valid json-looking model response"}'
    )
