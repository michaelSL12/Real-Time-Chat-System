from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class Room(Base):
    """
    Chat room.

    Fields:
        name: Unique room name.
        owner_id: User who created and owns this room.
        is_private: Whether membership or invitation is required.
        description: Optional short room description.
        created_at: Timestamp when the room was created.

    Relationships:
        owner: User who owns this room.
        messages: Messages posted in this room.
        members: Membership rows for users in this room.

    Cascades:
        Deleting a room also deletes its messages and membership rows.
    """

    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    description = Column(String(255), nullable=True)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)

    owner = relationship("User", back_populates="owned_rooms")
    messages = relationship(
        "Message",
        back_populates="room",
        cascade="all, delete-orphan",
    )
    members = relationship(
        "RoomMember",
        back_populates="room",
        cascade="all, delete-orphan",
    )


class RoomMember(Base):
    """
    Membership join table between users and rooms.

    A user can belong to many rooms, and a room can contain many users.
    This many-to-many relationship is represented by the room_members table.

    Fields:
        room_id: Joined room ID.
        user_id: Joined user ID.
        nickname: Optional per-room nickname for the user.
        created_at: Timestamp when the membership was created.

    Relationships:
        room: Room linked to this membership row.
        user: User linked to this membership row.

    Constraints:
        uq_room_user ensures a membership appears only once per
        (room_id, user_id) pair.
    """

    __tablename__ = "room_members"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    nickname = Column(String(50), nullable=True)

    room = relationship("Room", back_populates="members")
    user = relationship("User", back_populates="room_memberships")

    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_user"),
        Index("ix_room_members_room_user", "room_id", "user_id"),
    )


@event.listens_for(RoomMember, "before_insert")
def set_default_nickname(mapper, connection, target):
    if target.nickname:
        return
    
    result = connection.execute(
        select(User.username).where(User.id == target.user_id)
    ).scalar_one()

    target.nickname = result