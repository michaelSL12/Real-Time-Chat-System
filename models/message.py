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


class Message(Base):
    """
    Chat message posted in a room by a user.

    Fields:
        room_id: Room where the message was posted.
        user_id: Author of the message.
        content: Message text.
        created_at: Timestamp used for ordering and pagination.
        is_deleted: Whether the message was soft-deleted.
        deleted_at: When the message was soft-deleted.
        deleted_by_user_id: User who performed the deletion, if any.

    Relationships:
        room: Room that contains the message.
        user: Author of the message.
        deleted_by_user: User who deleted the message, if applicable.

    Indexing:
        Composite index (room_id, created_at, id) supports efficient
        cursor pagination by chronological order within a room.
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    room = relationship("Room", back_populates="messages")

    user = relationship(
        "User",
        back_populates="messages",
        foreign_keys=[user_id],
    )

    deleted_by_user = relationship(
        "User",
        foreign_keys=[deleted_by_user_id],
    )

    __table_args__ = (
        Index("ix_messages_room_created_id", "room_id", "created_at", "id"),
    )


class MessageRead(Base):
    """
    Per-user read state for a room.

    Stores the last message ID that a user has read in a given room.

    Fields:
        room_id: Room whose read state is being tracked.
        user_id: User whose read state is being tracked.
        last_read_message_id: Most recent message the user has marked as read.
        updated_at: Timestamp of the latest read-state update.

    Constraint:
        uq_room_user_read ensures a single row per (room_id, user_id).
    """

    __tablename__ = "message_reads"

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    last_read_message_id = Column(
    Integer,
    ForeignKey("messages.id", ondelete="SET NULL"),
    nullable=True,
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_user_read"),
    )