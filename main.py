from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session 
from sqlalchemy import select, and_, or_
from database import Base, engine, get_db
from models import Room, Message, RoomMember, User
from schemas import RoomCreate, RoomOut, MessageCreate, MessageOut, MessageListOut, UserCreate, UserOut, TokenOut
from auth import hash_password, verify_password, create_access_token, SECRET_KEY, ALGORITHM, get_current_user_optional, get_current_user
from jose import jwt, JWTError


from routers.auth_routes import router as auth_router
from routers.room_routes import router as room_router
from routers.message_routes import router as message_router
from routers.ws_routes import router as ws_router

app = FastAPI(title="Chat API", version="0.1.0")
app.include_router(auth_router)
app.include_router(room_router)
app.include_router(message_router)
app.include_router(ws_router)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@app.get("/health")
def health():
    return {"status": "ok"}

