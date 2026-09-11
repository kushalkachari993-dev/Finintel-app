from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter
from fastapi import Header
from fastapi import Security
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class AuthRoutes:
    router: APIRouter
    get_bearer_user: Callable
    get_authenticated_principal: Callable


def user_payload(user):
    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "active": user.active,
        "email_verified": user.email_verified,
    }


def create_auth_routes(
    *,
    get_clerk_authenticator: Callable,
    get_api_key_authenticator: Callable,
) -> AuthRoutes:
    router = APIRouter()

    def get_bearer_user(
        authorization: str = Header(default=""),
    ):
        if not authorization.startswith("Bearer "):
            return None

        return get_clerk_authenticator().authenticate(
            authorization.removeprefix("Bearer ").strip()
        )

    def get_authenticated_principal(
        authorization: str = Header(default=""),
        api_key: str = Header(
            default="",
            alias="X-API-Key",
        ),
    ):
        api_client = get_api_key_authenticator().authenticate(
            api_key
        )

        if api_client:
            return {
                "principal_id": f"client:{api_client.client_id}",
                "user": None,
                "api_client": api_client,
            }

        user = get_bearer_user(authorization)

        if user:
            return {
                "principal_id": f"clerk:{user.user_id}",
                "user": user,
                "api_client": None,
            }

        return None

    @router.get("/auth/me")
    def me(user=Security(get_bearer_user)):
        if not user:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "Invalid or missing bearer token.",
                },
            )

        return {
            "success": True,
            "user": user_payload(user),
        }

    return AuthRoutes(
        router=router,
        get_bearer_user=get_bearer_user,
        get_authenticated_principal=get_authenticated_principal,
    )
