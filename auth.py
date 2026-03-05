from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, WebSocket, status

from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User

import hashlib
import secrets
from models import User, RefreshToken


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# For learning: hardcode. Later move to env var.
SECRET_KEY = "CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECRET"
ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 20
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def access_expires_in_seconds() -> int:
    return ACCESS_TOKEN_EXPIRE_MINUTES * 60

def refresh_expires_in_seconds() -> int:
    return REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)



def decode_token_and_get_user(db: Session, token: str) -> User:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload.get("sub")
    if user_id is None:
        raise Exception("Invalid token")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise Exception("User not found")
    return user

def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not token:
        return None
    try:
        # reuse your existing decode logic
        user = decode_token_and_get_user(db, token)  # implement by extracting from your current get_current_user
        return user
    except Exception:
        return None

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive or missing user")
    return user


def issue_refresh_token(db: Session, user: User) -> str:
    raw = secrets.token_urlsafe(48)  # opaque token
    token_hash = _hash_refresh_token(raw)

    now = datetime.utcnow()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        revoked_at=None,
        replaced_by_token_hash=None,
    )
    db.add(rt)
    db.commit()
    return raw

def rotate_refresh_token(db: Session, raw_refresh_token: str) -> tuple[User, str]:
    token_hash = _hash_refresh_token(raw_refresh_token)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not rt:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if rt.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    if rt.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive or missing user")

    # rotation: revoke old + issue new
    new_raw = secrets.token_urlsafe(48)
    new_hash = _hash_refresh_token(new_raw)

    rt.revoked_at = datetime.utcnow()
    rt.replaced_by_token_hash = new_hash

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            revoked_at=None,
            replaced_by_token_hash=None,
        )
    )
    db.commit()

    return user, new_raw

def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    token_hash = _hash_refresh_token(raw_refresh_token)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not rt:
        # do not leak whether token exists; logout is idempotent
        return
    if rt.revoked_at is None:
        rt.revoked_at = datetime.utcnow()
        db.commit()

def revoke_all_refresh_tokens_for_user(db: Session, user_id: int) -> int:
    """
    Revokes all non-revoked refresh tokens for this user.
    Returns number of tokens revoked (optional).
    """
    now = datetime.utcnow()
    q = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )
    count = q.count()
    q.update({RefreshToken.revoked_at: now}, synchronize_session=False)
    db.commit()
    return count


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

def extract_ws_token(websocket: WebSocket) -> Optional[str]:
    auth = websocket.headers.get("authorization")
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

    return websocket.query_params.get("token")


def get_user_id_from_ws(websocket: WebSocket) -> int:
    token = extract_ws_token(websocket)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token (use Authorization header or ?token=)",
        )

    try:
        payload = decode_access_token(token)  
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Token missing subject (sub)")

    return int(sub)