# routers/auth_routes.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import UserCreate, UserOut, TokenOut, RefreshIn, RefreshOut, LogoutIn
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    issue_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
    access_expires_in_seconds,
    refresh_expires_in_seconds,
    get_current_user,
    revoke_all_refresh_tokens_for_user
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.execute(select(User).where(User.username == user_in.username)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

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
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == form_data.username)).scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": str(user.id)})
    refresh = issue_refresh_token(db, user)
    return {"access_token": token,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": access_expires_in_seconds(),
            "refresh_expires_in": refresh_expires_in_seconds(),
            }


@router.post("/refresh", response_model=RefreshOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    user, new_refresh = rotate_refresh_token(db, payload.refresh_token)
    new_access = create_access_token({"sub": str(user.id)})
    return {"access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "expires_in": access_expires_in_seconds(),
            "refresh_expires_in": refresh_expires_in_seconds()
            }

@router.post("/logout")
def logout(payload: LogoutIn, db: Session = Depends(get_db)):
    revoke_refresh_token(db, payload.refresh_token)
    return {"status": "logged_out"}


@router.post("/logout_all")
def logout_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    revoked = revoke_all_refresh_tokens_for_user(db, current_user.id)
    return {"status": "logged_out_all", "revoked": revoked}