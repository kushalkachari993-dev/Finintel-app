from dataclasses import dataclass
from functools import cached_property

import jwt
from jwt import PyJWKClient

from backend.config import settings


@dataclass(frozen=True)
class ClerkUser:
    user_id: str
    email: str
    full_name: str
    role: str
    active: bool = True
    email_verified: bool = True
    is_clerk: bool = True


class ClerkAuthenticator:
    def __init__(
        self,
        jwks_url: str | None = None,
        issuer: str | None = None,
        audience: str | None = None
    ):
        self.jwks_url = (
            settings.CLERK_JWKS_URL
            if jwks_url is None
            else jwks_url
        )
        self.issuer = (
            settings.CLERK_ISSUER
            if issuer is None
            else issuer
        )
        self.audience = (
            settings.CLERK_AUDIENCE
            if audience is None
            else audience
        )

    @property
    def enabled(self) -> bool:
        return bool(
            self.jwks_url
            and self.issuer
        )

    @cached_property
    def jwk_client(self):
        return PyJWKClient(
            self.jwks_url
        )

    def verify_token(
        self,
        token: str
    ) -> dict | None:
        if not self.enabled:
            return None

        try:
            signing_key = self.jwk_client.get_signing_key_from_jwt(
                token
            )
            options = {
                "verify_aud": bool(self.audience)
            }
            kwargs = {
                "algorithms": [
                    "RS256"
                ],
                "options": options
            }

            if self.issuer:
                kwargs[
                    "issuer"
                ] = self.issuer

            if self.audience:
                kwargs[
                    "audience"
                ] = self.audience

            return jwt.decode(
                token,
                signing_key.key,
                **kwargs
            )
        except Exception:
            return None

    @staticmethod
    def user_from_claims(
        claims: dict
    ) -> ClerkUser:
        email = (
            claims.get("email")
            or claims.get("email_address")
            or ""
        )
        full_name = (
            claims.get("name")
            or claims.get("full_name")
            or email
            or claims.get("sub", "")
        )
        public_metadata = claims.get(
            "public_metadata"
        )
        metadata_role = (
            public_metadata.get("role")
            if isinstance(public_metadata, dict)
            else None
        )
        role = (
            claims.get("role")
            or claims.get("org_role")
            or metadata_role
            or "user"
        )

        if role in {
            "org:admin",
            "admin"
        }:
            role = "admin"

        return ClerkUser(
            user_id=str(
                claims.get("sub", "")
            ),
            email=email,
            full_name=full_name,
            role=role
        )

    def authenticate(
        self,
        token: str
    ) -> ClerkUser | None:
        claims = self.verify_token(
            token
        )

        if not claims or not claims.get("sub"):
            return None

        return self.user_from_claims(
            claims
        )
