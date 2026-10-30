from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db.session import get_db
from app.schemas.requests import LoginRequest
from app.schemas.public import Session as PublicSession, User as PublicUser, to_iso_z
from app.services.auth_service import AuthService
from app.routes.deps import get_current_session, OrbitronAPIException

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=PublicSession)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db)
):
    # Origin check if origin header present
    origin = request.headers.get("Origin")
    if origin and origin != settings.orbitron_frontend_origin:
        raise OrbitronAPIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="ORIGIN_NOT_ALLOWED",
            message=f"Request origin '{origin}' is not permitted."
        )

    user = AuthService.authenticate_user(db, req.email, req.password)
    if not user:
        raise OrbitronAPIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Invalid email or password."
        )

    raw_token, session_obj = AuthService.create_session(db, user)

    # Set cookie: name orbitron_session, Path=/api/v1, HttpOnly=True, SameSite=lax
    response.set_cookie(
        key=settings.orbitron_session_cookie_name,
        value=raw_token,
        httponly=True,
        samesite="lax",
        path="/api/v1",
        secure=settings.orbitron_cookie_secure
    )

    return PublicSession(
        user=PublicUser(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            organization_id=user.organization_id,
            role=user.role
        ),
        csrf_token=session_obj.csrf_token,
        expires_at=to_iso_z(session_obj.expires_at)
    )

@router.get("/session", response_model=PublicSession)
def get_session_info(
    session_tuple=Depends(get_current_session)
):
    user, session_obj = session_tuple
    return PublicSession(
        user=PublicUser(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            organization_id=user.organization_id,
            role=user.role
        ),
        csrf_token=session_obj.csrf_token,
        expires_at=to_iso_z(session_obj.expires_at)
    )

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_tuple=Depends(get_current_session),
    db: DBSession = Depends(get_db)
):
    user, session_obj = session_tuple
    AuthService.revoke_session(db, session_obj, user)
    response.delete_cookie(
        key=settings.orbitron_session_cookie_name,
        path="/api/v1"
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
