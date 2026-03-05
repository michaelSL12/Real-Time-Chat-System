from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from datetime import datetime 

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    messages = relationship("Message", back_populates="user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    revoked_at = Column(DateTime, nullable=True, index=True)
    replaced_by_token_hash = Column(String(64), nullable=True)

    user = relationship("User", backref="refresh_tokens")

class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    description = Column(String(255), nullable=True)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    is_private = Column(Boolean, default=False, nullable=False)

    owner = relationship("User", backref="owned_rooms")
    messages = relationship("Message", back_populates="room", cascade="all, delete-orphan")
    members = relationship("RoomMember", back_populates="room", cascade="all, delete-orphan")


class RoomMember(Base):
    __tablename__ = "room_members"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    room = relationship("Room", back_populates="members")
    user = relationship("User", backref="room_memberships")

    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_user"),
        Index("ix_room_members_room_user", "room_id", "user_id"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    room = relationship("Room", back_populates="messages")
    user = relationship("User", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_room_created_id", "room_id", "created_at", "id"),
    )

class MessageRead(Base):
    __tablename__ = "message_reads"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    last_read_message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_user_read"),)    