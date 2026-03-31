"""
Authentication and token utilities for the chat backend.

This module is responsible for:
- password hashing and verification
- JWT access token creation and decoding
- current-user authentication dependencies for FastAPI routes
- refresh token issuance, rotation, and revocation
- WebSocket token extraction and authentication

Security model:
- Access tokens are JWTs signed with the application secret.
- Refresh tokens are random opaque strings stored only as SHA-256 hashes.
- Refresh token rotation is supported by revoking the old token and issuing a new one.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import RefreshToken, User
from settings import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)


TOKEN_URL = "/auth/login"
TOKEN_SUB_CLAIM = "sub"
TOKEN_EXP_CLAIM = "exp"

AUTH_HEADER_NAME = "authorization"
AUTH_SCHEME_BEARER = "bearer"
WS_QUERY_TOKEN_PARAM = "token"

REFRESH_TOKEN_LENGTH_BYTES = 48

AUTH_NOT_AUTHENTICATED_DETAIL = "Not authenticated"
AUTH_INVALID_TOKEN_DETAIL = "Invalid token"
AUTH_INACTIVE_OR_MISSING_USER_DETAIL = "Inactive or missing user"
AUTH_INVALID_REFRESH_TOKEN_DETAIL = "Invalid refresh token"
AUTH_REFRESH_TOKEN_REVOKED_DETAIL = "Refresh token revoked"
AUTH_REFRESH_TOKEN_EXPIRED_DETAIL = "Refresh token expired"
AUTH_MISSING_WS_TOKEN_DETAIL = (
    "Missing access token (use Authorization header or ?token=)"
)
AUTH_INVALID_OR_EXPIRED_WS_TOKEN_DETAIL = "Invalid or expired access token"
AUTH_TOKEN_MISSING_SUBJECT_DETAIL = "Token missing subject (sub)"

INVALID_TOKEN_ERROR = "Invalid token"
USER_NOT_FOUND_ERROR = "User not found"


# FastAPI helper that reads the bearer token from the Authorization header.
# auto_error=False allows support for both required-auth and optional-auth flows.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=TOKEN_URL, auto_error=False)


# Passlib hashing context for password hashing and verification.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def access_expires_in_seconds() -> int:
    """
    Return the access-token lifetime in seconds.
    """

    return ACCESS_TOKEN_EXPIRE_MINUTES * 60


def refresh_expires_in_seconds() -> int:
    """
    Return the refresh-token lifetime in seconds.
    """

    return REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using the configured password hasher.

    Args:
        password: Plaintext password provided by the user.

    Returns:
        A secure password hash suitable for database storage.
    """

    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored password hash.

    Args:
        password: Plaintext password attempt.
        hashed_password: Stored password hash from the database.

    Returns:
        True if the password matches the hash, otherwise False.
    """

    return pwd_context.verify(password, hashed_password)


def create_access_token(
    data: dict[str, object],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    The input payload is copied, an expiration claim ("exp") is added,
    and the token is signed using the configured secret key and algorithm.

    Args:
        data: Payload to encode into the JWT, typically including "sub".
        expires_delta: Optional custom expiration duration.
            If omitted, the default access-token lifetime is used.

    Returns:
        Encoded JWT access token as a string.
    """

    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({TOKEN_EXP_CLAIM: expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token_and_get_user(db: Session, token: str) -> User:
    """
    Decode a JWT access token and load the corresponding user from the database.

    Args:
        db: Active database session.
        token: Encoded JWT access token.

    Returns:
        The matching User object.

    Raises:
        ValueError: If the token is invalid, missing a subject, or the user
            does not exist.
    """

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload.get(TOKEN_SUB_CLAIM)

    if user_id is None:
        raise ValueError(INVALID_TOKEN_ERROR)

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise ValueError(USER_NOT_FOUND_ERROR)

    return user


def _hash_refresh_token(token: str) -> str:
    """
    Hash a refresh token using SHA-256 before storing or querying it.

    Args:
        token: Raw refresh token.

    Returns:
        Hex-encoded SHA-256 hash of the token.
    """

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """
    FastAPI dependency that returns the authenticated user if a valid token exists.

    This is useful for endpoints where authentication is optional.

    Args:
        token: Bearer token extracted from the Authorization header.
        db: Active database session.

    Returns:
        User if the token is valid, otherwise None.
    """

    if not token:
        return None

    try:
        return decode_token_and_get_user(db, token)
    except Exception:
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that requires a valid authenticated user.

    This dependency:
    - ensures a token is present
    - decodes and validates the token
    - loads the user from the database
    - rejects missing or inactive users

    Args:
        token: Bearer token extracted from the Authorization header.
        db: Active database session.

    Returns:
        Authenticated User object.

    Raises:
        HTTPException(401): If authentication fails for any reason.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED_DETAIL,
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get(TOKEN_SUB_CLAIM)
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=AUTH_INVALID_TOKEN_DETAIL,
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_TOKEN_DETAIL,
        )

    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INACTIVE_OR_MISSING_USER_DETAIL,
        )

    return user


def _create_refresh_token_record_helper(db: Session, user: User) -> tuple[str, str]:
    """
    Create a new refresh-token database record without committing it.

    This helper:
    - generates a secure random refresh token
    - hashes it for database storage
    - creates the RefreshToken ORM row
    - adds it to the session

    Args:
        db: Active database session.
        user: User who owns the refresh token.

    Returns:
        A tuple of:
        - raw refresh token (to return to the client)
        - hashed refresh token (to reference internally if needed)
    """

    raw = secrets.token_urlsafe(REFRESH_TOKEN_LENGTH_BYTES)
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
    return raw, token_hash


def issue_refresh_token(db: Session, user: User) -> str:
    """
    Issue a new refresh token for a user and persist it to the database.

    Args:
        db: Active database session.
        user: User receiving the refresh token.

    Returns:
        Raw refresh token string that should be returned to the client.
    """

    raw, _ = _create_refresh_token_record_helper(db, user)
    db.commit()
    return raw


def rotate_refresh_token(db: Session, raw_refresh_token: str) -> tuple[User, str]:
    """
    Rotate an existing refresh token.

    Rotation flow:
    - hash the incoming token
    - find the matching DB record
    - ensure it exists, is not revoked, and is not expired
    - ensure the owning user exists and is active
    - issue a new refresh token
    - revoke the old token and link it to the new token hash
    - commit both changes in one transaction

    Args:
        db: Active database session.
        raw_refresh_token: Raw refresh token provided by the client.

    Returns:
        A tuple of:
        - authenticated User
        - newly issued raw refresh token

    Raises:
        HTTPException(401): If the refresh token is invalid, revoked, expired,
        or belongs to an inactive/missing user.
    """

    token_hash = _hash_refresh_token(raw_refresh_token)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not rt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_REFRESH_TOKEN_DETAIL,
        )

    if rt.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_REFRESH_TOKEN_REVOKED_DETAIL,
        )

    if rt.expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_REFRESH_TOKEN_EXPIRED_DETAIL,
        )

    user = db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INACTIVE_OR_MISSING_USER_DETAIL,
        )

    new_raw, new_hash = _create_refresh_token_record_helper(db, user)

    rt.revoked_at = datetime.utcnow()
    rt.replaced_by_token_hash = new_hash

    db.commit()

    return user, new_raw


def _revoke_tokens_query_helper(q) -> int:
    """
    Revoke all non-revoked refresh tokens matched by a query.

    This helper updates the matched rows by setting revoked_at to the current UTC time.

    Args:
        q: SQLAlchemy query selecting RefreshToken rows to revoke.

    Returns:
        Number of rows that were revoked.
    """

    now = datetime.utcnow()
    count = q.count()
    if count:
        q.update({RefreshToken.revoked_at: now}, synchronize_session=False)
    return count


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    """
    Revoke a single refresh token if it exists and is not already revoked.

    This operation is intentionally idempotent:
    if the token does not exist, nothing happens.

    Args:
        db: Active database session.
        raw_refresh_token: Raw refresh token provided by the client.
    """
    token_hash = _hash_refresh_token(raw_refresh_token)

    q = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
    )

    _revoke_tokens_query_helper(q)
    db.commit()


def revoke_all_refresh_tokens_for_user(db: Session, user_id: int) -> int:
    """
    Revoke all active refresh tokens for a given user.

    Useful for "logout all sessions" functionality.

    Args:
        db: Active database session.
        user_id: ID of the user whose tokens should be revoked.

    Returns:
        Number of refresh tokens revoked.
    """

    q = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )

    count = _revoke_tokens_query_helper(q)
    db.commit()
    return count


def decode_access_token(token: str) -> dict[str, object]:
    """
    Decode and verify an access token.

    Args:
        token: JWT access token.

    Returns:
        Decoded JWT payload as a dictionary.

    Raises:
        jose.JWTError: If the token is invalid or expired.
    """

    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def extract_ws_token(websocket: WebSocket) -> str | None:
    """
    Extract an access token from a WebSocket connection request.

    Supported sources:
    - Authorization header: "Bearer <token>"
    - query string parameter: ?token=<token>

    Args:
        websocket: Incoming WebSocket connection.

    Returns:
        Token string if found, otherwise None.
    """

    auth = websocket.headers.get(AUTH_HEADER_NAME)
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == AUTH_SCHEME_BEARER:
            return parts[1]

    return websocket.query_params.get(WS_QUERY_TOKEN_PARAM)


def get_user_id_from_ws(websocket: WebSocket) -> int:
    """
    Authenticate a WebSocket connection and return the user ID from the token.

    This helper:
    - extracts the token from headers or query params
    - decodes and verifies it
    - reads the "sub" claim
    - returns it as an integer user ID

    Args:
        websocket: Incoming WebSocket connection.

    Returns:
        Authenticated user ID.

    Raises:
        HTTPException(401): If the token is missing, invalid, expired,
        or does not contain a subject claim.
    """
    
    token = extract_ws_token(websocket)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_MISSING_WS_TOKEN_DETAIL,
        )

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_OR_EXPIRED_WS_TOKEN_DETAIL,
        )

    sub = payload.get(TOKEN_SUB_CLAIM)
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_TOKEN_MISSING_SUBJECT_DETAIL,
        )

    return int(sub)