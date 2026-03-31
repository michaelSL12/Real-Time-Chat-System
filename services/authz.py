"""
Authorization helpers for room access and posting permissions.

This module contains reusable permission checks related to rooms.

Responsibilities:
- check whether a user is a member of a room
- enforce room access rules
- enforce membership rules for posting messages

This is authorization logic, not authentication:
- authentication answers "who is the user?"
- authorization answers "what is the user allowed to do?"
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import Room, RoomMember, User


DETAIL_LOGIN_REQUIRED_PRIVATE_ROOM = "Login required for private rooms"
DETAIL_NOT_ROOM_MEMBER = "You are not a member of this room"
DETAIL_JOIN_ROOM_BEFORE_POSTING = "Join the room before posting"


def is_member(db: Session, room_id: int, user_id: int) -> bool:
    """
    Check whether a user is a member of a given room.

    Args:
        db: Active database session.
        room_id: ID of the room being checked.
        user_id: ID of the user being checked.

    Returns:
        True if the user is a member of the room, otherwise False.
    """

    return db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == user_id,
    ).first() is not None


def require_room_access(db: Session, room: Room, user: User | None) -> None:
    """
    Enforce room access rules.

    Access policy:
    - public rooms are accessible to everyone
    - private rooms require authentication
    - room owners always have access
    - non-owners must be members to access a private room

    Args:
        db: Active database session.
        room: Room being accessed.
        user: Current authenticated user, or None if unauthenticated.

    Raises:
        HTTPException(401): If login is required for a private room.
        HTTPException(403): If the authenticated user is not allowed to access the room.
    """

    if not room.is_private:
        return

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=DETAIL_LOGIN_REQUIRED_PRIVATE_ROOM,
        )

    if not is_member(db, room.id, user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DETAIL_NOT_ROOM_MEMBER,
        )


def require_member_to_post(db: Session, room: Room, user: User) -> None:
    """
    Enforce posting permission rules for a room.

    Posting policy:
    - room owners may always post
    - other users must be members of the room before posting

    Args:
        db: Active database session.
        room: Room where the user wants to post.
        user: Current authenticated user.

    Raises:
        HTTPException(403): If the user is not allowed to post in the room.
    """

    if not is_member(db, room.id, user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DETAIL_JOIN_ROOM_BEFORE_POSTING,
        )