"""
Authentication API routes.

This module exposes the HTTP endpoints responsible for:
- user registration
- login with username/password
- access token refresh using refresh token rotation
- logout from the current session
- logout from all sessions

The router acts as the API layer only:
- request validation is handled by Pydantic schemas
- database access is done through SQLAlchemy sessions
- token/password logic is delegated to auth.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import (
    access_expires_in_seconds,
    create_access_token,
    get_current_user,
    hash_password,
    issue_refresh_token,
    refresh_expires_in_seconds,
    revoke_all_refresh_tokens_for_user,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from database import get_db
from models import User
from schemas import (
    LogoutIn,
    RefreshIn,
    RefreshOut,
    TokenOut,
    UserCreate,
    UserOut,
)


TOKEN_TYPE_BEARER = "bearer"
JWT_SUB_CLAIM = "sub"

DETAIL_USERNAME_EXISTS = "Username already exists"
DETAIL_INVALID_CREDENTIALS = "Invalid username or password"

STATUS_LOGGED_OUT = "logged_out"
STATUS_LOGGED_OUT_ALL = "logged_out_all"


# Router for all authentication-related endpoints.
router = APIRouter(prefix="/auth", tags=["auth"])


def _build_token_response(access_token: str, refresh_token: str) -> dict[str, object]:
    """
    Build a standard authentication token response payload.
    """
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": TOKEN_TYPE_BEARER,
        "expires_in": access_expires_in_seconds(),
        "refresh_expires_in": refresh_expires_in_seconds(),
    }


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    """
    Register a new user.

    Flow:
    1. Validate request body using UserCreate schema.
    2. Check whether the username already exists.
    3. Hash the incoming plaintext password.
    4. Create and save the new user.
    5. Return the created user as a safe UserOut response.

    Args:
        user_in: Request body containing username and plaintext password.
        db: Active database session injected by FastAPI.

    Returns:
        The created user as a UserOut response.

    Raises:
        HTTPException(409): If the username already exists.
    """

    existing = db.execute(
        select(User).where(User.username == user_in.username)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DETAIL_USERNAME_EXISTS,
        )

    user = User(
        username=user_in.username,
        hashed_password=hash_password(user_in.password),
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenOut)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenOut:
    """
    Authenticate a user and issue access/refresh tokens.

    This endpoint uses OAuth2PasswordRequestForm, which means the client sends
    credentials as form data rather than JSON.

    Flow:
    1. Look up the user by username.
    2. Verify the submitted password against the stored password hash.
    3. Create a short-lived access token.
    4. Create and persist a refresh token.
    5. Return both tokens along with expiration metadata.

    Args:
        form_data: OAuth2 login form containing username and password.
        db: Active database session injected by FastAPI.

    Returns:
        Token response containing:
        - access_token
        - refresh_token
        - token_type
        - expires_in
        - refresh_expires_in

    Raises:
        HTTPException(401): If username/password is invalid.
    """

    user = db.execute(
        select(User).where(User.username == form_data.username)
    ).scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=DETAIL_INVALID_CREDENTIALS,
        )

    access_token = create_access_token({JWT_SUB_CLAIM: str(user.id)})
    refresh_token = issue_refresh_token(db, user)

    return _build_token_response(access_token, refresh_token)


@router.post("/refresh", response_model=RefreshOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> RefreshOut:
    """
    Rotate a refresh token and issue a new access token.

    Flow:
    1. Validate the incoming refresh token payload.
    2. Rotate the existing refresh token in the database.
    3. Generate a new access token for the same user.
    4. Return the new access token and new refresh token.

    Args:
        payload: Request body containing the current refresh token.
        db: Active database session injected by FastAPI.

    Returns:
        New access/refresh token pair with expiration metadata.

    Raises:
        HTTPException(401): If the refresh token is invalid, revoked, expired,
        or belongs to an inactive/missing user.
    """

    user, new_refresh_token = rotate_refresh_token(db, payload.refresh_token)
    new_access_token = create_access_token({JWT_SUB_CLAIM: str(user.id)})

    return _build_token_response(new_access_token, new_refresh_token)


@router.post("/logout")
def logout(payload: LogoutIn, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Log out a single session by revoking its refresh token.

    This operation is intentionally idempotent:
    if the refresh token does not exist, the response is still successful.

    Args:
        payload: Request body containing the refresh token to revoke.
        db: Active database session injected by FastAPI.

    Returns:
        Simple status response confirming logout.
    """

    revoke_refresh_token(db, payload.refresh_token)
    return {"status": STATUS_LOGGED_OUT}


@router.post("/logout_all")
def logout_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | str]:
    """
    Log out the current user from all active sessions.

    This endpoint requires a valid access token.
    It revokes all non-revoked refresh tokens belonging to the authenticated user.

    Args:
        db: Active database session injected by FastAPI.
        current_user: Authenticated user resolved from the access token.

    Returns:
        Status response including the number of revoked refresh tokens.
    """

    revoked = revoke_all_refresh_tokens_for_user(db, current_user.id)
    return {"status": STATUS_LOGGED_OUT_ALL, "revoked": revoked}