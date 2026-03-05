# routers/ws_routes.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import get_db
from models import Message
from services.realtime import manager
from services import authz
from auth import get_user_id_from_ws
from services.rate_limit import message_limiter

from models import Room, User, MessageRead


router = APIRouter(tags=["ws"])


def _utc_iso(dt: datetime) -> str:
    # Ensure isoformat is stable (and timezone-aware)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


@router.websocket("/ws/rooms/{room_id}")
async def room_ws(room_id: int, websocket: WebSocket, db: Session = Depends(get_db)):
    # 1) Authenticate
    # NOTE: this may raise HTTPException. In websocket routes, FastAPI will close the connection.
    user_id = get_user_id_from_ws(websocket)

    # 2) Authorize room access (public ok, private requires membership)
    # Reuse your existing authorization layer:
    # - if you have require_room_access(room_id, user_id, db): call it
    # - otherwise: replicate your current logic here.
    room = db.get(Room, room_id)
    if not room:
        await websocket.close(code=1008)
        return

    user = db.get(User, user_id)
    if not user:
        await websocket.close(code=1008)
        return

    authz.require_room_access(db, room, user)

    # 3) Connect
    await manager.connect(room_id, websocket)

    # Optional: tell client it's connected
    await websocket.send_json({"type": "connected", "room_id": room_id, "user_id": user_id})

    try:
        while True:
            data: dict[str, Any] = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "read":
                message_id = data.get("message_id")
                if not isinstance(message_id, int):
                    await websocket.send_json({"type": "error", "detail": "message_id must be int"})
                    continue

                msg = db.get(Message, message_id)
                if not msg or msg.room_id != room_id:
                    await websocket.send_json({"type": "error", "detail": "Message not found in room"})
                    continue

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

                await manager.broadcast(room_id, {
                    "type": "read",
                    "room_id": room_id,
                    "user_id": user.id,
                    "last_read_message_id": mr.last_read_message_id,
                })
                continue

            if msg_type != "message":
                await websocket.send_json({"type": "error", "detail": "Unknown message type"})
                continue

            content = (data.get("content") or "").strip()
            if not content:
                await websocket.send_json({"type": "error", "detail": "Content is required"})
                continue

            allowed, retry_after = message_limiter.allow(user.id)
            if not allowed:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"Rate limit exceeded. Retry after {retry_after:.1f}s"
                })
                continue

            authz.require_member_to_post(db, room, user)

            m = Message(room_id=room_id, user_id=user_id, content=content)
            db.add(m)
            db.commit()
            db.refresh(m)

            payload = {
                "type": "message",
                "id": m.id,
                "room_id": m.room_id,
                "user_id": m.user_id,
                "content": m.content,
                "created_at": _utc_iso(m.created_at),
            }

            await manager.broadcast(room_id, payload)

    except WebSocketDisconnect:
        await manager.disconnect(room_id, websocket)
    except Exception:
        await manager.disconnect(room_id, websocket)
        # Let FastAPI close; optionally log here
        raise