# routers/room_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database import get_db
from models import Room, RoomMember, User
from schemas import RoomCreate, RoomOut
from auth import get_current_user

router = APIRouter(tags=["rooms"])


@router.post("/rooms", response_model=RoomOut)
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Room).filter(Room.name == payload.name).first()
    if existing:
        return existing

    room = Room(
        name=payload.name,
        description=getattr(payload, "description", None),  # supports your new field
        owner_id=current_user.id,
        is_private=payload.is_private,
    )
    db.add(room)
    db.commit()
    db.refresh(room)

    # owner is a member (needed for join-first posting rule)
    db.add(RoomMember(room_id=room.id, user_id=current_user.id))
    db.commit()

    return room


@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)):
    # only public rooms
    return db.query(Room).filter(Room.is_private == False).all()


@router.post("/rooms/{room_id}/join")
def join_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.is_private:
        raise HTTPException(status_code=403, detail="Cannot join a private room without invite")

    # already member or owner
    existing = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id
    ).first()
    if existing or room.owner_id == current_user.id:
        return {"status": "already_member"}

    db.add(RoomMember(room_id=room_id, user_id=current_user.id))
    db.commit()
    return {"status": "joined"}


@router.post("/rooms/{room_id}/invite/{user_id}")
def invite_to_room(
    room_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can invite users")

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # already member or owner
    existing = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == user_id
    ).first()
    if existing or room.owner_id == user_id:
        return {"status": "already_member"}

    db.add(RoomMember(room_id=room_id, user_id=user_id))
    db.commit()
    return {"status": "invited"}


@router.get("/me/accessible_rooms", response_model=list[RoomOut])
def my_accessible_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # clean select() to avoid SAWarning
    member_room_ids = select(RoomMember.room_id).where(RoomMember.user_id == current_user.id)

    rooms = db.query(Room).filter(
        or_(
            Room.owner_id == current_user.id,
            Room.id.in_(member_room_ids),
        )
    ).all()
    return rooms


@router.get("/me/owned_rooms", response_model=list[RoomOut])
def my_owned_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rooms = db.query(Room).filter(Room.owner_id == current_user.id).all()
    return rooms