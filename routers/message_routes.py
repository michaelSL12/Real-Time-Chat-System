"""
Message API routes.

This module exposes endpoints for:
- posting messages to a room
- listing messages in a room with cursor-style pagination
- marking messages as read for a user in a room
- retrieving the current user's read status for a room
- soft-deleting a room message as the room owner

It relies on:
- auth.py for current-user resolution
- services.authz for room access and posting permissions
- services.rate_limit for message throttling
- SQLAlchemy models for persistence
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session

from auth import get_current_user, get_current_user_optional
from database import get_db
from models import Message, MessageRead, Room, RoomMember, User
from schemas import MessageCreate, MessageListOut, MessageOut, RoomReadStatusResponse
from services.authz import require_member_to_post, require_room_access
from services.rate_limit import message_limiter


DETAIL_ROOM_NOT_FOUND = "Room not found"
DETAIL_MESSAGE_NOT_FOUND = "Message not found"
DETAIL_MESSAGE_NOT_FOUND_IN_ROOM = "Message not found in room"
DETAIL_NOT_ALLOWED_IN_ROOM = "Not allowed in this room"
DETAIL_ONLY_OWNER_CAN_DELETE_MESSAGES = "Only the room owner can delete messages"
DETAIL_DELETED_MESSAGE_CONTENT = "This message was deleted by the owner"

router = APIRouter(tags=["messages"])


@router.post("/rooms/{room_id}/messages", response_model=MessageOut)
def post_message(
    room_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOut:
    """
    Post a new message to a room.

    Flow:
    1. Load the room by ID.
    2. Ensure the room exists.
    3. Enforce posting permission rules.
    4. Apply per-user message rate limiting.
    5. Create and save the message.
    6. Return the created message.

    Args:
        room_id: ID of the room where the message will be posted.
        payload: Request body containing the message content.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user posting the message.

    Returns:
        The created message as a MessageOut response.

    Raises:
        HTTPException(404): If the room does not exist.
        HTTPException(403): If the user is not allowed to post in the room.
        HTTPException(429): If the user exceeds the message rate limit.
    """
    
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_ROOM_NOT_FOUND,
        )

    require_member_to_post(db, room, current_user)

    allowed, retry_after = message_limiter.allow(current_user.id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after:.1f}s",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    message = Message(
        room_id=room_id,
        user_id=current_user.id,
        content=payload.content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return message


def apply_desc_cursor(
    db: Session,
    q: SAQuery,
    room_id: int,
    before_id: int | None,
) -> SAQuery:
    """
    Apply descending-pagination cursor logic to a message query.

    Args:
        db: Active SQLAlchemy session.
        q: Current SQLAlchemy query for messages.
        room_id: ID of the room being listed.
        before_id: Pivot message ID for descending pagination.

    Returns:
        The updated query with descending cursor filtering applied, if valid.
    """

    if before_id is None:
        return q

    pivot = db.get(Message, before_id)
    if not pivot or pivot.room_id != room_id:
        return q

    return q.filter(
        or_(
            Message.created_at < pivot.created_at,
            and_(
                Message.created_at == pivot.created_at,
                Message.id < pivot.id,
            ),
        )
    )


def apply_asc_cursor(
    db: Session,
    q: SAQuery,
    room_id: int,
    after_id: int | None,
) -> SAQuery:
    """
    Apply ascending-pagination cursor logic to a message query.

    Args:
        db: Active SQLAlchemy session.
        q: Current SQLAlchemy query for messages.
        room_id: ID of the room being listed.
        after_id: Pivot message ID for ascending pagination.

    Returns:
        The updated query with ascending cursor filtering applied, if valid.
    """

    if after_id is None:
        return q

    pivot = db.get(Message, after_id)
    if not pivot or pivot.room_id != room_id:
        return q

    return q.filter(
        or_(
            Message.created_at > pivot.created_at,
            and_(
                Message.created_at == pivot.created_at,
                Message.id > pivot.id,
            ),
        )
    )


def apply_message_ordering(q: SAQuery, order: str) -> SAQuery:
    """
    Apply message ordering to the query.

    Args:
        q: Current SQLAlchemy query for messages.
        order: Sort direction, expected to be either "asc" or "desc".

    Returns:
        The query with ordering applied.
    """
    
    if order == "desc":
        return q.order_by(Message.created_at.desc(), Message.id.desc())
    return q.order_by(Message.created_at.asc(), Message.id.asc())


def serialize_messages(
    db: Session,
    items: list[Message],
) -> list[dict[str, object | None]]:
    """
    Convert Message ORM objects into API response dictionaries.

    Args:
        db: Active SQLAlchemy session.
        items: Message ORM objects to serialize.

    Returns:
        A list of dictionaries shaped for the message list response.
    """

    message_items: list[dict[str, object | None]] = []

    for msg in items:
        membership = db.query(RoomMember).filter(
            RoomMember.room_id == msg.room_id,
            RoomMember.user_id == msg.user_id,
        ).first()

        message_items.append(
            {
                "id": msg.id,
                "room_id": msg.room_id,
                "user_id": msg.user_id,
                "content": msg.content,
                "created_at": msg.created_at,
                "username": msg.user.username if msg.user else None,
                "display_name": getattr(msg.user, "display_name", None)
                if msg.user
                else None,
                "nickname": membership.nickname if membership else None,
                "is_deleted": msg.is_deleted,
                "deleted_at": msg.deleted_at,
                "deleted_by_user_id": msg.deleted_by_user_id,
            }
        )

    return message_items

@router.get("/rooms/{room_id}/messages", response_model=MessageListOut)
def list_messages(
    room_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    before_id: int | None = None,
    after_id: int | None = None,
    current_user: User | None = Depends(get_current_user_optional),
) -> MessageListOut:
    """
    List messages in a room with cursor-style pagination.

    Pagination behavior:
    - order="desc": returns newest-to-oldest messages
      and uses before_id as the pagination cursor
    - order="asc": returns oldest-to-newest messages
      and uses after_id as the pagination cursor

    Cursor logic:
    - the pivot message is loaded by ID
    - pagination compares (created_at, id) for stable ordering
    - this avoids ambiguity when two messages share the same timestamp

    Access rules:
    - public rooms can be viewed by anyone
    - private rooms require authorization via require_room_access()

    Args:
        room_id: ID of the room whose messages should be listed.
        db: Active database session injected by FastAPI.
        limit: Maximum number of messages to return.
        order: Either "asc" or "desc".
        before_id: Cursor for descending pagination ("older than this message").
        after_id: Cursor for ascending pagination ("newer than this message").
        current_user: Authenticated user if present, otherwise None.

    Returns:
        A paginated message list containing:
        - items: current page of messages
        - next_cursor: ID of the last item in the current page, if any

    Raises:
        HTTPException(404): If the room does not exist.
        HTTPException(401/403): If the user is not allowed to access the room.
    """

    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_ROOM_NOT_FOUND,
        )

    require_room_access(db, room, current_user)

    q = db.query(Message).filter(Message.room_id == room_id)
    if order == "desc":
        q = apply_desc_cursor(db, q, room_id, before_id)
    else:
        q = apply_asc_cursor(db, q, room_id, after_id)
    q = apply_message_ordering(q, order)

    items = q.limit(limit).all()
    next_cursor = items[-1].id if items else None

    message_items = serialize_messages(db, items)

    return {
        "items": message_items,
        "next_cursor": next_cursor,
    }


@router.post("/rooms/{room_id}/read/{message_id}")
def mark_read(
    room_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    """
    Mark a message as read for the current user in a given room.

    This endpoint stores per-user read progress in the MessageRead table.

    Flow:
    1. Load and validate the room.
    2. Enforce room access rules.
    3. Load and validate the target message.
    4. Find existing MessageRead row for (room_id, user_id).
    5. If none exists, create one.
    6. If one exists, only move the read marker forward.
    7. Update updated_at and commit.

    Args:
        room_id: ID of the room containing the message.
        message_id: ID of the message being marked as read.
        db: Active database session injected by FastAPI.
        user: Authenticated user marking the message as read.

    Returns:
        A small status payload containing:
        - room_id
        - user_id
        - last_read_message_id

    Raises:
        HTTPException(404): If the room does not exist, or if the message
        does not exist in that room.
        HTTPException(401/403): If the user is not allowed to access the room.
    """

    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_ROOM_NOT_FOUND,
        )

    require_room_access(db, room, user)

    message = db.get(Message, message_id)
    if not message or message.room_id != room_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_MESSAGE_NOT_FOUND_IN_ROOM,
        )

    mr = db.query(MessageRead).filter(
        MessageRead.room_id == room_id,
        MessageRead.user_id == user.id,
    ).first()

    now = datetime.utcnow()

    if mr is None:
        mr = MessageRead(
            room_id=room_id,
            user_id=user.id,
            last_read_message_id=message_id,
            updated_at=now,
        )
        db.add(mr)
    else:
        if message_id > mr.last_read_message_id:
            mr.last_read_message_id = message_id
        mr.updated_at = now

    db.commit()

    return {
        "room_id": room_id,
        "user_id": user.id,
        "last_read_message_id": mr.last_read_message_id,
    }


@router.get("/rooms/{room_id}/read", response_model=RoomReadStatusResponse)
def get_room_read_status(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RoomReadStatusResponse:
    """
    Return the current user's read status for a room.

    This includes the last read message ID and, when available,
    a small snapshot of that message's content and timestamp.

    Args:
        room_id: ID of the room.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user requesting read status.

    Returns:
        Read status information for the current user in the room.

    Raises:
        HTTPException(404): If the room does not exist.
        HTTPException(401/403): If the user is not allowed to access the room.
    """

    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_ROOM_NOT_FOUND,
        )

    require_room_access(db, room, current_user)

    last_read = (
        db.query(MessageRead)
        .filter(
            MessageRead.user_id == current_user.id,
            MessageRead.room_id == room_id,
        )
        .order_by(desc(MessageRead.last_read_message_id))
        .first()
    )

    if not last_read:
        return RoomReadStatusResponse(room_id=room_id)

    message = db.get(Message, last_read.last_read_message_id)

    return RoomReadStatusResponse(
        room_id=room_id,
        last_read_message_id=last_read.last_read_message_id,
        last_read_message_content=message.content if message else None,
        last_read_message_created_at=message.created_at if message else None,
    )


@router.delete("/rooms/{room_id}/messages/{message_id}", response_model=MessageOut)
def delete_room_message(
    room_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOut:
    """
    Soft-delete a room message.

    Only the room owner may delete messages through this endpoint.
    The message row remains in the database, but its content is replaced
    and deletion metadata is recorded.

    Args:
        room_id: ID of the room containing the message.
        message_id: ID of the message to delete.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user attempting the deletion.

    Returns:
        The updated message record.

    Raises:
        HTTPException(404): If the room or message does not exist.
        HTTPException(403): If the current user is not the room owner.
    """

    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_ROOM_NOT_FOUND,
        )

    if room.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DETAIL_ONLY_OWNER_CAN_DELETE_MESSAGES,
        )

    message = db.get(Message, message_id)
    if not message or message.room_id != room_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_MESSAGE_NOT_FOUND,
        )

    if message.is_deleted:
        return message

    message.content = DETAIL_DELETED_MESSAGE_CONTENT
    message.is_deleted = True
    message.deleted_at = datetime.utcnow()
    message.deleted_by_user_id = current_user.id

    db.commit()
    db.refresh(message)

    return message