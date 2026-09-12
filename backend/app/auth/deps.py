"""Authentication dependencies for FastAPI routes.

- ``get_current_user``  - resolves the ``Authorization: Bearer <token>`` header
- ``require_permission`` - RBAC gate factory (returns a dependency)

The backend is the sole authorization authority; these dependencies protect
every sensitive route.
"""

from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status

from app import models
from app.auth.repository import UserRepository, make_user_repository
from app.auth.roles import role_has_permission
from app.config import settings
from app.security import SessionIdentity, TokenError, decode_signed_token

CurrentUser = models.User

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_auth_secret() -> str:
    return settings.resolved_auth_secret()


def _bearer_token_from(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer "):].strip()
    return token or None


def get_current_user(
    request: Request,
    repository: UserRepository = Depends(make_user_repository),
    secret: str = Depends(get_auth_secret),
) -> models.User:
    token = _bearer_token_from(request)
    if not token:
        raise _credentials_exc
    try:
        payload = decode_signed_token(token, secret)
        identity = SessionIdentity.from_payload(payload)
    except TokenError:
        raise _credentials_exc

    if identity.token_type != "access":
        raise _credentials_exc

    user = repository.get_by_username(identity.username)
    if not user or str(user.id) != identity.user_id:
        raise _credentials_exc
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is disabled.",
        )
    repository.touch_last_active(identity.user_id)
    return user


def require_permission(permission: str) -> Callable:
    def _dependency(
        user: models.User = Depends(get_current_user),
    ) -> models.User:
        if not role_has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return _dependency


def current_user_id(user: models.User = Depends(get_current_user)) -> str:
    return str(user.id)