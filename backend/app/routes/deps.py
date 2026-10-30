import json
import secrets
from typing import Tuple, Optional
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db.session import get_db
from app.db.models import User, SessionModel, ServicePrincipal, ServiceCredential, ApplicationState
from app.services.auth_service import AuthService
from app.services.snapshot_service import SnapshotService
from app.services.idempotency import IdempotencyService, canonical_hash

class OrbitronAPIException(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[list] = None
    ):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or []

def get_current_session(
    request: Request,
    db: DBSession = Depends(get_db)
) -> Tuple[User, SessionModel]:
    cookie_token = request.cookies.get(settings.orbitron_session_cookie_name)
    if not cookie_token:
        # Also check Authorization: Bearer for convenience if provided
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            cookie_token = auth_header[7:]

    if not cookie_token:
        raise OrbitronAPIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHENTICATED",
            message="Authentication session cookie or bearer token is missing."
        )

    res = AuthService.get_session(db, cookie_token)
    if not res:
        raise OrbitronAPIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="SESSION_EXPIRED",
            message="Session is invalid, expired, or has been revoked."
        )

    user, session_obj = res

    # Check origin for mutation requests
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        origin = request.headers.get("Origin")
        if origin and origin != settings.orbitron_frontend_origin:
            raise OrbitronAPIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="ORIGIN_NOT_ALLOWED",
                message=f"Request origin '{origin}' is not permitted."
            )

        # Validate CSRF token for mutations
        csrf_header = request.headers.get("X-CSRF-Token")
        if not AuthService.validate_csrf(session_obj, csrf_header):
            raise OrbitronAPIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="CSRF_INVALID",
                message="X-CSRF-Token is missing or does not match active session."
            )

    return user, session_obj

def get_current_user(session_tuple: Tuple[User, SessionModel] = Depends(get_current_session)) -> User:
    return session_tuple[0]

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "network_admin":
        raise OrbitronAPIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="Action requires network_admin role."
        )
    return user

def get_service_principal(
    request: Request,
    db: DBSession = Depends(get_db)
) -> Tuple[ServicePrincipal, ServiceCredential]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise OrbitronAPIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHENTICATED",
            message="Authorization bearer header is required for service APIs."
        )

    bearer_token = auth_header[7:]
    res = AuthService.validate_service_credential(db, bearer_token)
    if not res:
        raise OrbitronAPIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIAL",
            message="Bearer credential is invalid, expired, or revoked."
        )

    return res
