# routers/message_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from services.rate_limit import message_limiter
from datetime import datetime

from database import get_db
from models import Room, Message, User, MessageRead
from schemas import MessageCreate, MessageOut, MessageListOut
from auth import get_current_user, get_current_user_optional
from services.authz import require_room_access, require_member_to_post

router = APIRouter(tags=["messages"])


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session


@router.post("/rooms/{room_id}/messages", response_model=MessageOut)
def post_message(
    room_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    require_member_to_post(db, room, current_user)
    
    allowed, retry_after = message_limiter.allow(current_user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {retry_after:.1f}s",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    msg = Message(room_id=room_id, user_id=current_user.id, content=payload.content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("/rooms/{room_id}/messages", response_model=MessageListOut)
def list_messages(
    room_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    before_id: int | None = None,
    after_id: int | None = None,
    current_user: User | None = Depends(get_current_user_optional),
):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    require_room_access(db, room, current_user)

    q = db.query(Message).filter(Message.room_id == room_id)

    if order == "desc":
        # cursor: before_id means "older than pivot"
        if before_id is not None:
            pivot = db.get(Message, before_id)
            if pivot and pivot.room_id == room_id:
                q = q.filter(
                    or_(
                        Message.created_at < pivot.created_at,
                        and_(Message.created_at == pivot.created_at, Message.id < pivot.id),
                    )
                )
        q = q.order_by(Message.created_at.desc(), Message.id.desc())
    else:
        # order == "asc": cursor is after_id means "newer than pivot"
        if after_id is not None:
            pivot = db.get(Message, after_id)
            if pivot and pivot.room_id == room_id:
                q = q.filter(
                    or_(
                        Message.created_at > pivot.created_at,
                        and_(Message.created_at == pivot.created_at, Message.id > pivot.id),
                    )
                )
        q = q.order_by(Message.created_at.asc(), Message.id.asc())

    items = q.limit(limit).all()
    next_cursor = items[-1].id if items else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/rooms/{room_id}/read/{message_id}")
def mark_read(
    room_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "Room not found")

    require_room_access(db, room, user)

    msg = db.get(Message, message_id)
    if not msg or msg.room_id != room_id:
        raise HTTPException(404, "Message not found in room")

    # upsert
    mr = db.query(MessageRead).filter(
        MessageRead.room_id == room_id,
        MessageRead.user_id == user.id,
    ).first()

    if mr is None:
        mr = MessageRead(room_id=room_id, user_id=user.id, last_read_message_id=message_id)
        db.add(mr)
    else:
        # Only move forward
        if message_id > mr.last_read_message_id:
            mr.last_read_message_id = message_id
        mr.updated_at = datetime.utcnow()

    db.commit()
    return {"room_id": room_id, "user_id": user.id, "last_read_message_id": mr.last_read_message_id}