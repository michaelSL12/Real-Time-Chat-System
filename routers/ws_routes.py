"""
WebSocket routes for realtime room communication.

This module is responsible for:
- authenticating WebSocket clients
- authorizing room access
- accepting room connections
- receiving realtime events from clients
- broadcasting messages and read receipts to connected clients
- handling disconnect cleanup

Supported incoming event types:
- "ping": keepalive / health check
- "read": update per-user read state for a room
- "message": send a chat message to the room
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from auth import get_user_id_from_ws
from database import get_db
from models import Message, MessageRead, Room, RoomMember, User
from services import authz
from services.rate_limit import message_limiter
from services.realtime import manager


EVENT_TYPE_CONNECTED = "connected"
EVENT_TYPE_ERROR = "error"
EVENT_TYPE_MESSAGE = "message"
EVENT_TYPE_PING = "ping"
EVENT_TYPE_PONG = "pong"
EVENT_TYPE_READ = "read"

DETAIL_UNKNOWN_MESSAGE_TYPE = "Unknown message type"
DETAIL_ROOM_NOT_FOUND = "Room not found"
DETAIL_USER_NOT_FOUND = "User not found"
DETAIL_CONTENT_REQUIRED = "Content is required"
DETAIL_MESSAGE_ID_MUST_BE_INT = "message_id must be int"
DETAIL_MESSAGE_NOT_FOUND_IN_ROOM = "Message not found in room"

WS_CLOSE_POLICY_VIOLATION = 1008

router = APIRouter(tags=["ws"])


def _utc_iso(dt: datetime) -> str:
    """
    Convert a datetime to a stable ISO-8601 UTC string.

    If the datetime is naive, UTC timezone is attached before serialization.

    Args:
        dt: Datetime to serialize.

    Returns:
        ISO-8601 formatted datetime string.
    """

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _load_ws_room_and_user(db: Session, room_id: int, user_id: int) -> tuple[Room, User]:
    """
    Load and validate the room and user for a WebSocket connection.

    Also enforces room access authorization.

    Args:
        db: Active database session.
        room_id: Target room ID from the WebSocket path.
        user_id: Authenticated user ID from the access token.

    Returns:
        Tuple of (room, user).

    Raises:
        ValueError: If room or user does not exist.
        HTTPException: If authorization fails inside require_room_access().
    """

    room = db.get(Room, room_id)
    if not room:
        raise ValueError(DETAIL_ROOM_NOT_FOUND)

    user = db.get(User, user_id)
    if not user:
        raise ValueError(DETAIL_USER_NOT_FOUND)

    authz.require_room_access(db, room, user)
    return room, user


async def _handle_ping(websocket: WebSocket) -> None:
    """
    Respond to a ping event from the client.

    Args:
        websocket: Active WebSocket connection.
    """

    await websocket.send_json({"type": EVENT_TYPE_PONG})


async def _handle_read_event(
    db: Session,
    room_id: int,
    user: User,
    data: dict[str, Any],
) -> None:
    """
    Handle a read-receipt event.

    Expected payload:
        {"type": "read", "message_id": <int>}

    Behavior:
    - validates message_id
    - ensures the message exists in the target room
    - creates or updates the user's MessageRead row
    - only moves the read marker forward
    - broadcasts the updated read state to room members

    Args:
        db: Active database session.
        room_id: Room where the event occurred.
        user: Authenticated user sending the event.
        data: Incoming WebSocket event payload.
    """

    message_id = data.get("message_id")
    if not isinstance(message_id, int):
        raise ValueError(DETAIL_MESSAGE_ID_MUST_BE_INT)

    msg = db.get(Message, message_id)
    if not msg or msg.room_id != room_id:
        raise ValueError(DETAIL_MESSAGE_NOT_FOUND_IN_ROOM)

    mr = db.query(MessageRead).filter(
        MessageRead.room_id == room_id,
        MessageRead.user_id == user.id,
    ).first()

    if mr is None:
        mr = MessageRead(
            room_id=room_id,
            user_id=user.id,
            last_read_message_id=message_id,
            updated_at=datetime.utcnow(),
        )
        db.add(mr)
    else:
        if message_id > mr.last_read_message_id:
            mr.last_read_message_id = message_id
        mr.updated_at = datetime.utcnow()

    db.commit()

    await manager.broadcast(
        room_id,
        {
            "type": EVENT_TYPE_READ,
            "room_id": room_id,
            "user_id": user.id,
            "last_read_message_id": mr.last_read_message_id,
        },
        db,
    )


async def _handle_message_event(
    db: Session,
    room: Room,
    user: User,
    data: dict[str, Any],
) -> None:
    """
    Handle an incoming chat message event.

    Expected payload:
        {"type": "message", "content": "<text>"}

    Behavior:
    - validates content
    - applies per-user message rate limiting
    - enforces posting authorization
    - saves the message to the database
    - broadcasts the created message only to connected room members

    Args:
        db: Active database session.
        room: Target room.
        user: Authenticated user sending the message.
        data: Incoming WebSocket event payload.

    Raises:
        ValueError: If content is missing or empty.
        PermissionError: If rate limit is exceeded.
        HTTPException: If room posting authorization fails.
    """

    authz.require_member_to_post(db, room, user)

    content = (data.get("content") or "").strip()
    if not content:
        raise ValueError(DETAIL_CONTENT_REQUIRED)

    allowed, retry_after = message_limiter.allow(user.id)
    if not allowed:
        raise PermissionError(f"Rate limit exceeded. Retry after {retry_after:.1f}s")

    message = Message(
        room_id=room.id,
        user_id=user.id,
        content=content,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    membership = db.query(RoomMember).filter(
        RoomMember.room_id == room.id,
        RoomMember.user_id == user.id,
    ).first()

    await manager.broadcast(
        room.id,
        {
            "type": EVENT_TYPE_MESSAGE,
            "id": message.id,
            "room_id": message.room_id,
            "user_id": message.user_id,
            "content": message.content,
            "created_at": _utc_iso(message.created_at),
            "username": user.username,
            "display_name": getattr(user, "display_name", None),
            "nickname": membership.nickname if membership else None,
            "is_deleted": message.is_deleted,
            "deleted_at": _utc_iso(message.deleted_at) if message.deleted_at else None,
            "deleted_by_user_id": message.deleted_by_user_id,
        },
        db,
    )


async def _handle_ws_event(
    websocket: WebSocket,
    db: Session,
    room: Room,
    user: User,
    data: dict[str, Any],
) -> None:
    """
    Route a single incoming WebSocket event to the correct handler.

    Supported event types:
    - ping
    - read
    - message

    Unknown event types return an error payload to the sender.

    Args:
        websocket: Active WebSocket connection.
        db: Active database session.
        room: Target room.
        user: Authenticated user.
        data: Incoming WebSocket event payload.
    """

    msg_type = data.get("type")

    if msg_type == EVENT_TYPE_PING:
        await _handle_ping(websocket)
        return

    if msg_type == EVENT_TYPE_READ:
        try:
            await _handle_read_event(db, room.id, user, data)
        except ValueError as e:
            await websocket.send_json({"type": EVENT_TYPE_ERROR, "detail": str(e)})
        return

    if msg_type == EVENT_TYPE_MESSAGE:
        try:
            await _handle_message_event(db, room, user, data)
        except ValueError as e:
            await websocket.send_json({"type": EVENT_TYPE_ERROR, "detail": str(e)})
        except PermissionError as e:
            await websocket.send_json({"type": EVENT_TYPE_ERROR, "detail": str(e)})
        return

    await websocket.send_json(
        {"type": EVENT_TYPE_ERROR, "detail": DETAIL_UNKNOWN_MESSAGE_TYPE}
    )


@router.websocket("/ws/rooms/{room_id}")
async def room_ws(
    room_id: int,
    websocket: WebSocket,
    db: Session = Depends(get_db),
) -> None:
    """
    Main WebSocket endpoint for a room.

    Connection flow:
    1. Authenticate the user from the WebSocket token.
    2. Load the room and user from the database.
    3. Enforce room access authorization.
    4. Register the WebSocket connection with the realtime manager.
    5. Receive and process incoming events in a loop.
    6. Disconnect cleanly on client disconnect or unexpected errors.

    Args:
        room_id: ID of the room from the URL path.
        websocket: Active WebSocket connection.
        db: Active database session injected by FastAPI.
    """
    
    user_id = get_user_id_from_ws(websocket)

    try:
        room, user = _load_ws_room_and_user(db, room_id, user_id)
    except Exception:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
        return

    await manager.connect(room_id, websocket, user_id)
    await websocket.send_json(
        {
            "type": EVENT_TYPE_CONNECTED,
            "room_id": room_id,
            "user_id": user_id,
        }
    )

    try:
        while True:
            data: dict[str, Any] = await websocket.receive_json()
            await _handle_ws_event(websocket, db, room, user, data)

    except WebSocketDisconnect:
        await manager.disconnect(room_id, websocket)
    except Exception:
        await manager.disconnect(room_id, websocket)
        raise