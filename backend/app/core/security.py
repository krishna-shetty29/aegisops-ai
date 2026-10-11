import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt import PyJWKClient

from app.services.security_audit import write_security_audit

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]


@lru_cache
def get_jwks_client() -> PyJWKClient:
    jwks_url = os.getenv("ENTRA_JWKS_URL")

    if not jwks_url:
        raise RuntimeError("ENTRA_JWKS_URL is missing.")

    return PyJWKClient(jwks_url)


def _audit_denied_access(
    request: Request,
    principal: Principal,
) -> None:
    """
    Store safe authorization metadata only.

    This function never stores bearer tokens, headers, PATs,
    database URLs, prompts, raw logs, or request bodies.
    """
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)

    try:
        write_security_audit(
            actor_subject=principal.subject,
            actor_role=",".join(sorted(principal.roles)) or "none",
            action="authorization_checked",
            resource_type="api_endpoint",
            resource_id=str(route_path)[:255],
            outcome="denied",
            summary=(
                "The authenticated user did not have a required "
                "role for this endpoint."
            ),
        )
    except Exception:
        # Never allow an audit-storage failure to accidentally
        # grant access to a forbidden endpoint.
        pass


def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    """
    Local mode is for development only and accepts requests only
    from this machine. Entra mode validates signed bearer tokens.
    """
    auth_mode = os.getenv("AUTH_MODE", "local").strip().lower()

    if auth_mode == "local":
        client_host = request.client.host if request.client else ""

        if client_host not in {"127.0.0.1", "::1"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Local-only API access is required.",
            )

        return Principal(
            subject="local-developer",
            roles=frozenset({"viewer", "reviewer", "admin", "agent"}),
        )

    if auth_mode != "entra":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )

    audience = os.getenv("ENTRA_API_AUDIENCE")
    issuer = os.getenv("ENTRA_ISSUER")

    if not audience or not issuer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Microsoft Entra authentication is not configured.",
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(
            credentials.credentials
        )

        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "sub"]},
        )

    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The access token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    raw_roles = claims.get("roles", [])

    if not isinstance(raw_roles, list):
        raw_roles = []

    roles = frozenset(
        str(role).strip().lower() for role in raw_roles if str(role).strip()
    )

    return Principal(
        subject=str(claims["sub"]),
        roles=roles,
    )


def require_roles(
    *allowed_roles: str,
) -> Callable[..., Principal]:
    """
    Return a FastAPI dependency that permits only the given roles.
    """
    allowed = frozenset(role.strip().lower() for role in allowed_roles if role.strip())

    def dependency(
        request: Request,
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        if not principal.roles.intersection(allowed):
            _audit_denied_access(request, principal)

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this action.",
            )

        return principal

    return dependency
