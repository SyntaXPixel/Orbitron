import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db.models import User, SessionModel, ServicePrincipal, ServiceCredential, AuditEntry
from app.schemas.public import Session as PublicSession, User as PublicUser, to_iso_z

ph = PasswordHasher()

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHash):
        return False

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

class AuthService:
    @classmethod
    def authenticate_user(cls, db: DBSession, email: str, password: str) -> Optional[User]:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @classmethod
    def create_session(cls, db: DBSession, user: User) -> Tuple[str, SessionModel]:
        raw_session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        token_hash = hash_token(raw_session_token)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=settings.orbitron_session_ttl_seconds)

        session_id = secrets.token_hex(16)
        session_obj = SessionModel(
            id=session_id,
            session_token_hash=token_hash,
            csrf_token=csrf_token,
            user_id=user.id,
            expires_at=expires_at,
            revoked=False,
            created_at=now
        )
        db.add(session_obj)

        audit = AuditEntry(
            id=f"audit-{secrets.token_hex(8)}",
            actor_name=user.display_name,
            action="login",
            resource_type="session",
            resource_id=session_id,
            outcome="succeeded",
            message=f"User {user.email} logged in successfully",
            timestamp=now,
            clock_basis="server"
        )
        db.add(audit)
        db.commit()
        db.refresh(session_obj)
        return raw_session_token, session_obj

    @classmethod
    def get_session(cls, db: DBSession, raw_session_token: str) -> Optional[Tuple[User, SessionModel]]:
        token_hash = hash_token(raw_session_token)
        now = datetime.now(timezone.utc)
        session_obj = (
            db.query(SessionModel)
            .filter(SessionModel.session_token_hash == token_hash, SessionModel.revoked == False)
            .first()
        )
        if not session_obj:
            return None

        # Check expiry using server time
        exp = session_obj.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            session_obj.revoked = True
            db.commit()
            return None

        user = db.query(User).filter(User.id == session_obj.user_id).first()
        if not user:
            return None

        return user, session_obj

    @classmethod
    def revoke_session(cls, db: DBSession, session_obj: SessionModel, user: Optional[User] = None):
        session_obj.revoked = True
        now = datetime.now(timezone.utc)
        actor = user.display_name if user else "user"
        audit = AuditEntry(
            id=f"audit-{secrets.token_hex(8)}",
            actor_name=actor,
            action="logout",
            resource_type="session",
            resource_id=session_obj.id,
            outcome="succeeded",
            message=f"Session revoked on logout",
            timestamp=now,
            clock_basis="server"
        )
        db.add(audit)
        db.commit()

    @classmethod
    def validate_csrf(cls, session_obj: SessionModel, csrf_token_header: Optional[str]) -> bool:
        if not csrf_token_header:
            return False
        return hmac.compare_digest(session_obj.csrf_token, csrf_token_header)

    @classmethod
    def validate_service_credential(cls, db: DBSession, bearer_token: str) -> Optional[Tuple[ServicePrincipal, ServiceCredential]]:
        token_hash = hash_token(bearer_token)
        now = datetime.now(timezone.utc)
        cred = (
            db.query(ServiceCredential)
            .filter(ServiceCredential.token_hash == token_hash, ServiceCredential.revoked == False)
            .first()
        )
        if not cred:
            return None

        if cred.expires_at is not None:
            exp = cred.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                return None

        principal = db.query(ServicePrincipal).filter(ServicePrincipal.id == cred.principal_id).first()
        if not principal:
            return None

        return principal, cred
