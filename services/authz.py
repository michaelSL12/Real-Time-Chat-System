from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Room, RoomMember, User


def is_member(db: Session, room_id: int, user_id: int) -> bool:
    return db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == user_id
    ).first() is not None

def require_room_access(db: Session, room: Room, user: User | None):
    if not room.is_private:
        return
    if user is None:
        raise HTTPException(status_code=401, detail="Login required for private rooms")
    if room.owner_id == user.id:
        return
    if not is_member(db, room.id, user.id):
        raise HTTPException(status_code=403, detail="You are not a member of this room")

def require_member_to_post(db: Session, room: Room, user: User):
    if room.owner_id == user.id:
        return
    if not is_member(db, room.id, user.id):
        raise HTTPException(status_code=403, detail="Join the room before posting")