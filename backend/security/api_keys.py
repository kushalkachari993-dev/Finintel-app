import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Any

from backend.config import settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class APIClient:
    client_id: str
    name: str
    key_hash: str
    role: str = "user"
    active: bool = True
    rate_limit_per_minute: int | None = None


class APIKeyAuthenticator:
    """Authenticates API keys against configured client records."""

    def __init__(
        self,
        clients_json: str | None = None,
        legacy_api_key: str | None = None
    ):
        self.clients = self._load_clients(
            clients_json=clients_json,
            legacy_api_key=legacy_api_key
        )

    @staticmethod
    def hash_key(
        api_key: str
    ) -> str:
        return hashlib.sha256(
            api_key.encode("utf-8")
        ).hexdigest()

    def _load_clients(
        self,
        clients_json: str | None,
        legacy_api_key: str | None
    ) -> list[APIClient]:
        clients = []

        if clients_json:
            try:
                raw_clients = json.loads(
                    clients_json
                )
                clients.extend(
                    self._parse_client(
                        raw_client
                    )
                    for raw_client in raw_clients
                )

            except Exception:
                logger.exception(
                    "api_clients_json_invalid"
                )
                raise RuntimeError(
                    "API_CLIENTS_JSON must be valid JSON."
                )

        if legacy_api_key:
            clients.append(
                APIClient(
                    client_id="default",
                    name="Default API client",
                    key_hash=self.hash_key(
                        legacy_api_key
                    ),
                    role="admin",
                    active=True,
                    rate_limit_per_minute=settings.RATE_LIMIT_PER_MINUTE
                )
            )

        return clients

    def _parse_client(
        self,
        raw_client: dict[str, Any]
    ) -> APIClient:
        key_hash = (
            raw_client.get("key_hash")
            or raw_client.get("api_key_sha256")
        )
        raw_key = raw_client.get(
            "api_key"
        )

        if raw_key:
            key_hash = self.hash_key(
                raw_key
            )

        if (
            not raw_client.get("client_id")
            or not key_hash
        ):
            raise RuntimeError(
                "Each API client needs client_id and key_hash."
            )

        return APIClient(
            client_id=str(
                raw_client["client_id"]
            ),
            name=str(
                raw_client.get(
                    "name",
                    raw_client["client_id"]
                )
            ),
            key_hash=str(
                key_hash
            ),
            role=str(
                raw_client.get(
                    "role",
                    "user"
                )
            ),
            active=bool(
                raw_client.get(
                    "active",
                    True
                )
            ),
            rate_limit_per_minute=raw_client.get(
                "rate_limit_per_minute"
            )
        )

    def authenticate(
        self,
        api_key: str | None
    ) -> APIClient | None:
        if not api_key:
            return None

        provided_hash = self.hash_key(
            api_key
        )

        for client in self.clients:
            if (
                client.active
                and hmac.compare_digest(
                    provided_hash,
                    client.key_hash
                )
            ):
                return client

        return None

    def reload_from_settings(self):
        self.clients = self._load_clients(
            clients_json=settings.API_CLIENTS_JSON,
            legacy_api_key=settings.APP_API_KEY
        )
