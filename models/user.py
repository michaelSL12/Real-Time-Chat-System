from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    """
    Application user.

    Fields:
        id: Primary key.
        username: Unique username used for login.
        hashed_password: Password hash; plaintext passwords are never stored.
        is_active: Logical flag used to disable accounts without deleting them.

    Relationships:
        messages: Messages authored by this user.
        refresh_tokens: Refresh token records owned by this user.
        owned_rooms: Rooms created and owned by this user.
        room_memberships: Membership rows linking this user to rooms.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    messages = relationship(
        "Message",
        back_populates="user",
        foreign_keys="Message.user_id",
    )

    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    owned_rooms = relationship(
        "Room",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    room_memberships = relationship(
        "RoomMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )