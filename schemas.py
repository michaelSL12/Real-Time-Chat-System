from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional, Literal

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=72)

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    username: str
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str    
    token_type: str = "bearer"
    expires_in: int  
    refresh_expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10)

class RefreshOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  
    refresh_expires_in: int


class LogoutIn(BaseModel):
    refresh_token: str = Field(min_length=10)


class RoomCreate(BaseModel):
    name: str
    is_private: bool = False
    description: Optional[str] = None 

class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_private: bool
    owner_id: int
    description: Optional[str] = None
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    room_id: int
    user_id: int
    content: str
    created_at: datetime

class MessageListOut(BaseModel):
    items: List[MessageOut]
    next_cursor: Optional[int] = None