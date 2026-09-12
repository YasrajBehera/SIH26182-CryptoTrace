"""Authentication and user-administration API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app import models
from app.audit.service import AuditService, get_audit_service_dep
from app.auth.deps import get_current_user, require_permission
from app.auth.models import (
    ChangePasswordRequest,
    LoginRequest,
    RoleOut,
    TokenResponse,
    UserCreate,
    UserListResponse,
    UserOut,
    UserUpdate,
)
from app.auth.repository import (
    DuplicateUserError,
    InvalidRoleError,
    UserNotFoundError,
    UserRepository,
    make_user_repository,
)
from app.auth.service import (
    DisabledAccountError,
    InvalidCredentialsError,
    PasswordMismatchError,
    UserService,
)
from app.security import PasswordPolicyError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/v1/admin/users", tags=["admin"])


def _client_ip(request: Request) -> str | None:
    try:
        return request.client.host if request.client else None
    except Exception:
        return None


def get_auth_service_dep(
    repository: UserRepository = Depends(make_user_repository),
    audit_service: AuditService = Depends(get_audit_service_dep),
) -> UserService:
    return UserService(repository=repository, audit_service=audit_service)


def _to_out(user: models.User) -> UserOut:
    return UserOut(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        role=user.role,
        title=user.title,
        is_active=user.is_active,
        is_demo=user.is_demo,
        last_active_at=user.last_active_at.isoformat() if user.last_active_at else None,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        200: {"description": "Authenticated"},
        401: {"description": "Invalid credentials or disabled account"},
        429: {"description": "Rate limited"},
    },
)
def login(
    body: LoginRequest,
    request: Request,
    service: UserService = Depends(get_auth_service_dep),
) -> TokenResponse:
    """Authenticate with username + password and receive a signed token."""
    try:
        return service.authenticate(body.username, body.password, ip=_client_ip(request))
    except (InvalidCredentialsError, DisabledAccountError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc


@router.post(
    "/logout",
    responses={200: {"description": "Logged out"}},
)
def logout(
    request: Request,
    user: models.User = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service_dep),
) -> dict:
    """Stateless logout: records the event; the client discards the token."""
    audit_service.record_event(
        user=user.username,
        action="LOGOUT",
        resource="auth",
        resource_id="",
        result="success",
        ip=_client_ip(request),
    )
    return {"detail": "Signed out.", "ok": True}


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)) -> UserOut:
    return _to_out(user)


@router.post("/change-password", response_model=dict)
def change_password(
    body: ChangePasswordRequest,
    user: models.User = Depends(get_current_user),
    service: UserService = Depends(get_auth_service_dep),
) -> dict:
    try:
        service.change_password(user.username, body.current_password, body.new_password)
    except (PasswordMismatchError, UserNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return {"detail": "Password updated."}


# ---- Admin user management (guarded by user.manage) ------------------------


@admin_router.get("", response_model=UserListResponse)
def list_users(
    service: UserService = Depends(get_auth_service_dep),
    _current_user=Depends(require_permission("user.manage")),
) -> UserListResponse:
    users = service.list_users()
    return UserListResponse(users=users, source=service.repository.__class__.__name__)


@admin_router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User created"},
        409: {"description": "Username already taken"},
        422: {"description": "Invalid role or password policy"},
    },
)
def create_user(
    body: UserCreate,
    service: UserService = Depends(get_auth_service_dep),
    _current_user=Depends(require_permission("user.manage")),
) -> UserOut:
    try:
        return service.create_user(body)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidRoleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateUserError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@admin_router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    service: UserService = Depends(get_auth_service_dep),
    _current_user=Depends(require_permission("user.manage")),
) -> UserOut:
    try:
        return service.update_user(user_id, body)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidRoleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@admin_router.delete(
    "/{user_id}",
    response_model=UserOut,
    responses={200: {"description": "User disabled"}, 404: {"description": "Not found"}},
)
def disable_user(
    user_id: str,
    service: UserService = Depends(get_auth_service_dep),
    _current_user=Depends(require_permission("user.manage")),
) -> UserOut:
    """Disable (soft-delete) an account; re-enable via PATCH is_active=True."""
    try:
        return service.update_user(user_id, UserUpdate(is_active=False))
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.get("/roles", response_model=list[RoleOut])
def list_roles(
    service: UserService = Depends(get_auth_service_dep),
    _current_user=Depends(require_permission("user.manage")),
) -> list[RoleOut]:
    return [RoleOut(**r) for r in service.roles()]