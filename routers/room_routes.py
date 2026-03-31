"""
Room API routes.

This module exposes the HTTP endpoints responsible for:
- creating rooms
- listing public rooms
- joining public rooms
- inviting users to private/public rooms
- listing rooms accessible to the current user
- listing rooms owned by the current user
- renaming rooms
- deleting rooms
- updating a user's nickname within a room

This router handles room-level actions and relies on:
- SQLAlchemy models for persistence
- Pydantic schemas for request/response validation
- auth.py for authenticated-user resolution
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Room, RoomMember, User
from schemas import (
    RoomCreate,
    RoomInviteByUsername,
    RoomNicknameUpdate,
    RoomOut,
    RoomRename,
)


DETAIL_ROOM_NOT_FOUND = "Room not found"
DETAIL_USER_NOT_FOUND = "User not found"
DETAIL_ROOM_NAME_EXISTS = "Room name already exists"
DETAIL_CANNOT_JOIN_PRIVATE_ROOM = "Cannot join a private room without invite"
DETAIL_ONLY_OWNER_CAN_INVITE = "Only the owner can invite users"
DETAIL_ONLY_OWNER_CAN_DELETE = "Only the owner can delete the room"
DETAIL_ROOM_ACCESS_FORBIDDEN = "Not allowed to access this room"
DETAIL_ROOM_UPDATE_FORBIDDEN = "Not allowed to update this room"
DETAIL_NOT_A_ROOM_MEMBER = "You are not a member of this room"
DETAIL_NOT_A_PRIVATE_ROOM = "Owner can invite just in a private room"
DETAIL_NAME_ALREADY_TAKEN = "This name already been taken by other user of the this room chat"

STATUS_ALREADY_MEMBER = "already_member"
STATUS_JOINED = "joined"
STATUS_INVITED = "invited"
STATUS_DELETED = "deleted"


router = APIRouter(tags=["rooms"])


@router.post("/rooms", response_model=RoomOut)
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RoomOut:
    """
    Create a new room owned by the current authenticated user.

    Flow:
    1. Validate request body using RoomCreate.
    2. Check whether a room with the same name already exists.
    3. Create the room with the current user as owner.
    4. Save the room to the database.
    5. Add the owner as a RoomMember as well.
    6. Return the created room.

    Args:
        payload: Request body containing room creation data.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user creating the room.

    Returns:
        The created room.

    Note:
        The owner is also inserted into RoomMember so that room membership
        checks remain consistent across the application.
    """

    existing = db.query(Room).filter(Room.name == payload.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=DETAIL_ROOM_NAME_EXISTS,
        )

    room = Room(
        name=payload.name,
        description=getattr(payload, "description", None),
        owner_id=current_user.id,
        is_private=payload.is_private,
    )

    db.add(room)
    db.commit()
    db.refresh(room)
    
    db.add(RoomMember(room_id=room.id, user_id=current_user.id))
    db.commit()

    return room


@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)) -> list[RoomOut]:
    """
    List all public rooms.

    This endpoint intentionally excludes private rooms.

    Args:
        db: Active database session injected by FastAPI.

    Returns:
        List of public rooms.
    """

    return db.query(Room).filter(Room.is_private.is_(False)).all()


@router.post("/rooms/{room_id}/join")
def join_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Join a public room.

    Flow:
    1. Load the room by ID.
    2. Reject if the room does not exist.
    3. Reject if the room is private.
    4. If the user is already a member (or owner), return already_member.
    5. Otherwise create a RoomMember row and return joined.

    Args:
        room_id: ID of the room to join.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user attempting to join.

    Returns:
        A small status dictionary indicating whether the user joined
        or was already a member.

    Raises:
        HTTPException(404): If the room does not exist.
        HTTPException(403): If the room is private.
    """

    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_ROOM_NOT_FOUND,
        )

    if room.is_private:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DETAIL_CANNOT_JOIN_PRIVATE_ROOM,
        )

    already_member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id,
    ).first()

    if already_member:
        return {"status": STATUS_ALREADY_MEMBER}

    db.add(RoomMember(room_id=room_id, user_id=current_user.id))
    db.commit()

    return {"status": STATUS_JOINED}



@router.get("/me/accessible_rooms", response_model=list[RoomOut])
def my_accessible_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RoomOut]:
    """
    Return all rooms the current user can access.

    Accessible rooms are rooms where the current user is a member

    Args:
        db: Active database session injected by FastAPI.
        current_user: Authenticated user.

    Returns:
        List of rooms accessible to the current user.
    """

    member_room_ids = select(RoomMember.room_id).where(
        RoomMember.user_id == current_user.id
    )

    rooms = db.query(Room).filter(
            Room.id.in_(member_room_ids)
    ).all()

    return rooms


@router.get("/me/owned_rooms", response_model=list[RoomOut])
def my_owned_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RoomOut]:
    """
    Return all rooms owned by the current authenticated user.

    Args:
        db: Active database session injected by FastAPI.
        current_user: Authenticated user.

    Returns:
        List of rooms owned by the current user.
    """

    return db.query(Room).filter(Room.owner_id == current_user.id).all()


@router.patch("/rooms/{room_id}", response_model=RoomOut)
def update_room(
    room_id: int,
    payload: RoomRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RoomOut:
    """
    Rename an existing room.

    A room may be renamed by any user who has access to it, meaning:
    - the room owner
    - a room member

    Args:
        room_id: ID of the room to rename.
        payload: Request body containing the new room name.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user attempting the update.

    Returns:
        The updated room.

    Raises:
        HTTPException(404): If the room does not exist.
        HTTPException(403): If the current user does not have access to the room.
        HTTPException(400): If another room already uses the same name.
    """

    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_ROOM_NOT_FOUND,
        )

    membership = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id,
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DETAIL_ROOM_UPDATE_FORBIDDEN,
        )

    existing = db.query(Room).filter(
        Room.name == payload.name,
        Room.id != room_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=DETAIL_ROOM_NAME_EXISTS,
        )

    room.name = payload.name
    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms/{room_id}", response_model=RoomOut)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RoomOut:
    """
    Return a single room if the current user has access to it.

    Access is granted when the current user is either:
    - the room owner
    - a room member

    Args:
        room_id: ID of the room to retrieve.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user requesting the room.

    Returns:
        The requested room.

    Raises:
        HTTPException(404): If the room does not exist.
        HTTPException(403): If the user is not allowed to access the room.
    """

    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_ROOM_NOT_FOUND,
        )

    membership = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id,
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DETAIL_ROOM_ACCESS_FORBIDDEN,
        )

    return room


@router.post("/rooms/{room_id}/invite")
def invite_to_room_by_username(
    room_id: int,
    payload: RoomInviteByUsername,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Invite a user to a room by username.

    Only the room owner may invite users.

    Args:
        room_id: ID of the room.
        payload: Request body containing the target username.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user performing the invite.

    Returns:
        A small status dictionary indicating whether the target user
        was newly invited or was already a member.

    Raises:
        HTTPException(404): If the room or target user does not exist.
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
            detail=DETAIL_ONLY_OWNER_CAN_INVITE,
        )

    target = db.query(User).filter(User.username == payload.username).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DETAIL_USER_NOT_FOUND,
        )

    existing = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == target.id,
    ).first()

    if existing or room.owner_id == target.id:
        return {"status": STATUS_ALREADY_MEMBER}

    db.add(RoomMember(room_id=room_id, user_id=target.id))
    db.commit()

    return {"status": STATUS_INVITED}


@router.delete("/rooms/{room_id}")
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Delete a room owned by the current user.

    Args:
        room_id: ID of the room to delete.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user attempting the deletion.

    Returns:
        Simple status response confirming deletion.

    Raises:
        HTTPException(404): If the room does not exist.
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
            detail=DETAIL_ONLY_OWNER_CAN_DELETE,
        )

    db.delete(room)
    db.commit()

    return {"status": STATUS_DELETED}


@router.patch("/rooms/{room_id}/my-nickname")
def update_my_room_nickname(
    room_id: int,
    payload: RoomNicknameUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | str | None]:
    """
    Update the current user's nickname within a room.

    The user must already be a member of the room.

    Args:
        room_id: ID of the room.
        payload: Request body containing the new nickname or null/empty value.
        db: Active database session injected by FastAPI.
        current_user: Authenticated user updating their nickname.

    Returns:
        A small payload containing the room ID, user ID, and stored nickname.

    Raises:
        HTTPException(403): If the current user is not a room member.
    """

    membership = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id,
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DETAIL_NOT_A_ROOM_MEMBER,
        )

    name_already_taken = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.nickname == payload.nickname,
    ).first()

    if name_already_taken:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DETAIL_NAME_ALREADY_TAKEN,
        )

    membership.nickname = payload.nickname.strip() if payload.nickname else None
    db.commit()
    db.refresh(membership)

    return {
        "room_id": room_id,
        "user_id": current_user.id,
        "nickname": membership.nickname,
    }