"""
Pydantic schemas for request validation and response serialization.

These schemas define the API contract between the backend and clients:
- input schemas validate incoming request data
- output schemas shape safe JSON responses
- ORM-compatible output schemas can be created from SQLAlchemy model objects
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """
    Request body for user registration.

    Validation:
        - username must be between 3 and 50 characters
        - password must be between 6 and 72 characters

    Note:
        The password is accepted here in plain text only so it can be hashed
        before storage. It should never be returned in any response schema.
    """

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=72)


class UserOut(BaseModel):
    """
    Safe user representation returned by the API.

    This schema excludes sensitive fields such as hashed_password.
    It can be built directly from a SQLAlchemy User object because
    from_attributes=True is enabled.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_active: bool


class TokenOut(BaseModel):
    """
    Response returned after successful authentication.

    Fields:
        access_token: Short-lived JWT used for authenticated requests.
        refresh_token: Long-lived token used to obtain a new access token.
        token_type: Authentication scheme used by clients in the Authorization header.
        expires_in: Access token lifetime in seconds.
        refresh_expires_in: Refresh token lifetime in seconds.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class RefreshIn(BaseModel):
    """
    Request body for refreshing an expired or expiring access token.
    """

    refresh_token: str = Field(min_length=10)


class RefreshOut(BaseModel):
    """
    Response returned after a successful token refresh.

    This typically includes a new access token and a rotated refresh token.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class LogoutIn(BaseModel):
    """
    Request body for logout.

    The refresh token is used so the server can revoke the correct session.
    """

    refresh_token: str = Field(min_length=10)


class RoomCreate(BaseModel):
    """
    Request body for creating a chat room.

    Fields:
        name: Room name.
        is_private: Whether the room requires membership or invitation.
        description: Optional short room description.
    """

    name: str = Field(min_length=1, max_length=100)
    is_private: bool = False
    description: str | None = None




class RoomOut(BaseModel):
    """
    Room representation returned by the API.

    Can be created directly from a SQLAlchemy Room object.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_private: bool
    owner_id: int
    description: str | None = None
    created_at: datetime


class RoomRename(BaseModel):
    """
    Request body for renaming a room.
    """

    name: str = Field(min_length=1, max_length=100)


class MessageCreate(BaseModel):
    """
    Request body for creating a new message.

    Validation:
        - content cannot be empty
        - content length is capped at 2000 characters
    """

    content: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    """
    Message representation returned by the API.

    Includes database-generated metadata such as the message ID
    and creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    user_id: int
    content: str
    created_at: datetime
    username: str | None = None
    display_name: str | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by_user_id: int | None = None
    nickname: str | None = None


class MessageListOut(BaseModel):
    """
    Paginated message list response.

    Fields:
        items: Current page of messages.
        next_cursor: Cursor for fetching the next page, if any.
    """

    items: list[MessageOut]
    next_cursor: int | None = None


class RoomReadStatusResponse(BaseModel):
    """
    Response describing the current user's read state for a room.
    """

    room_id: int
    last_read_message_id: int | None = None
    last_read_message_content: str | None = None
    last_read_message_created_at: datetime | None = None


class RoomInviteByUsername(BaseModel):
    """
    Request body for inviting a user to a room by username.
    """

    username: str = Field(min_length=1, max_length=50)


class RoomNicknameUpdate(BaseModel):
    """
    Request body for updating the current user's nickname in a room.
    """

    nickname: str | None = Field(default=None, max_length=50)