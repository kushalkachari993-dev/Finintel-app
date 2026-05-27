import pytest

from backend.security import APIKeyAuthenticator


def test_authenticator_supports_multiple_named_clients():
    authenticator = APIKeyAuthenticator(
        clients_json=(
            "["
            "{\"client_id\":\"frontend\",\"api_key\":\"front-key\"},"
            "{\"client_id\":\"admin\",\"api_key\":\"admin-key\",\"role\":\"admin\"}"
            "]"
        ),
        legacy_api_key=None
    )

    frontend = authenticator.authenticate(
        "front-key"
    )
    admin = authenticator.authenticate(
        "admin-key"
    )

    assert frontend is not None
    assert frontend.client_id == "frontend"
    assert admin is not None
    assert admin.role == "admin"


def test_authenticator_rejects_inactive_client():
    authenticator = APIKeyAuthenticator(
        clients_json=(
            "[{\"client_id\":\"disabled\","
            "\"api_key\":\"secret\","
            "\"active\":false}]"
        ),
        legacy_api_key=None
    )

    assert authenticator.authenticate(
        "secret"
    ) is None


def test_authenticator_requires_valid_client_records():
    with pytest.raises(
        RuntimeError
    ):
        APIKeyAuthenticator(
            clients_json="[{\"client_id\":\"missing-key\"}]",
            legacy_api_key=None
        )
