"""
WebSocket room tests.

This file tests the real-time WebSocket behavior of the application.
It verifies connection authentication, access control for public and
private rooms, ping/pong behavior, message sending rules, database
persistence, and broadcasting messages to multiple connected clients.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.testclient import WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect

from models import Message, User
from tests.helper import auth_headers, create_room, join_room, login, register, unique_user


CONNECTED_EVENT_TYPE = "connected"
ERROR_EVENT_TYPE = "error"
MESSAGE_EVENT_TYPE = "message"
PING_EVENT_TYPE = "ping"
PONG_EVENT_TYPE = "pong"

HTTP_200_OK = 200
HTTP_204_NO_CONTENT = 204


def test_ws_connect_with_query_token(client: TestClient, db_session: Session):
    """
    Verify that a WebSocket connection succeeds when the token is passed
    in the query string.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "room-query", is_private=False)
    room_id = room["id"]

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token}") as ws:
        payload = ws.receive_json()
        assert payload["type"] == CONNECTED_EVENT_TYPE
        assert payload["room_id"] == room_id


def test_ws_connect_with_auth_header(client: TestClient, db_session: Session):
    """
    Verify that a WebSocket connection succeeds when the token is passed
    in the Authorization header.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "room-header", is_private=False)
    room_id = room["id"]

    with client.websocket_connect(
        f"/ws/rooms/{room_id}",
        headers=auth_headers(token),
    ) as ws:
        payload = ws.receive_json()
        assert payload["type"] == CONNECTED_EVENT_TYPE
        assert payload["room_id"] == room_id


def test_ws_rejects_missing_token(client: TestClient, db_session: Session):
    """
    Verify that a WebSocket connection is rejected when no token is provided.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "room-missing-token", is_private=False)
    room_id = room["id"]

    with pytest.raises((WebSocketDenialResponse, WebSocketDisconnect)):
        with client.websocket_connect(f"/ws/rooms/{room_id}"):
            pass


def test_ws_rejects_invalid_token(client: TestClient, db_session: Session):
    """
    Verify that a WebSocket connection is rejected when the token is invalid.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "room-invalid-token", is_private=False)
    room_id = room["id"]

    bad_token = "this.is.not.a.jwt"

    with pytest.raises((WebSocketDenialResponse, WebSocketDisconnect)):
        with client.websocket_connect(f"/ws/rooms/{room_id}?token={bad_token}"):
            pass


def test_ws_private_room_denied_if_not_member(client: TestClient, db_session: Session):
    """
    Verify that a user cannot connect to a private room unless they are a member.
    """
    owner_username, owner_password = unique_user()
    register(client, owner_username, owner_password)
    owner_token = login(client, owner_username, owner_password)["access_token"]

    room = create_room(client, owner_token, "private-denied", is_private=True)
    room_id = room["id"]

    other_username, other_password = unique_user()
    register(client, other_username, other_password)
    other_token = login(client, other_username, other_password)["access_token"]

    with pytest.raises((WebSocketDenialResponse, WebSocketDisconnect)):
        with client.websocket_connect(f"/ws/rooms/{room_id}?token={other_token}"):
            pass


def test_ws_private_room_allowed_after_invite(client: TestClient, db_session: Session):
    """
    Verify that an invited user can connect to a private room.
    """
    owner_username, owner_password = unique_user()
    register(client, owner_username, owner_password)
    owner_token = login(client, owner_username, owner_password)["access_token"]

    room = create_room(client, owner_token, "private-invited", is_private=True)
    room_id = room["id"]

    other_username, other_password = unique_user()
    register(client, other_username, other_password)
    other_token = login(client, other_username, other_password)["access_token"]

    invited_user_id = db_session.query(User).filter(User.username == other_username).one().id

    invite_response = client.post(
        f"/rooms/{room_id}/invite/{invited_user_id}",
        headers=auth_headers(owner_token),
    )
    assert invite_response.status_code in (HTTP_200_OK, HTTP_204_NO_CONTENT), invite_response.text

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={other_token}") as ws:
        payload = ws.receive_json()
        assert payload["type"] == CONNECTED_EVENT_TYPE


def test_ws_ping_pong(client: TestClient, db_session: Session):
    """
    Verify that the WebSocket endpoint responds to ping messages.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "room-ping", is_private=False)
    room_id = room["id"]

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": PING_EVENT_TYPE})

        payload = ws.receive_json()
        assert payload["type"] == PONG_EVENT_TYPE


def test_ws_send_message_requires_membership(client: TestClient, db_session: Session):
    """
    Verify that sending a message requires room membership.
    """
    owner_username, owner_password = unique_user()
    register(client, owner_username, owner_password)
    owner_token = login(client, owner_username, owner_password)["access_token"]

    room = create_room(client, owner_token, "room-membership", is_private=False)
    room_id = room["id"]

    other_username, other_password = unique_user()
    register(client, other_username, other_password)
    other_token = login(client, other_username, other_password)["access_token"]

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={other_token}") as ws:
        ws.receive_json()
        ws.send_json({"type": MESSAGE_EVENT_TYPE, "content": "hello"})

        try:
            payload = ws.receive_json()
            assert payload.get("type") == ERROR_EVENT_TYPE or "detail" in payload
        except (WebSocketDisconnect, WebSocketDenialResponse):
            pass


def test_ws_send_message_persists_and_broadcasts(client: TestClient, db_session: Session):
    """
    Verify that a valid message is stored in the database and broadcast
    back through the WebSocket connection.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "room-persist", is_private=False)
    room_id = room["id"]

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token}") as ws:
        ws.receive_json()

        ws.send_json({"type": MESSAGE_EVENT_TYPE, "content": "hello"})
        payload = ws.receive_json()

        assert payload["type"] == MESSAGE_EVENT_TYPE
        assert payload["content"] == "hello"
        assert payload["room_id"] == room_id
        assert isinstance(payload["id"], int)

        message_id = payload["id"]
        message = db_session.query(Message).filter(Message.id == message_id).one()
        assert message.content == "hello"


def test_ws_broadcast_to_two_clients(client: TestClient, db_session: Session):
    """
    Verify that a message sent by one connected client is broadcast
    to all connected clients in the same room.
    """
    username_one, password_one = unique_user()
    register(client, username_one, password_one)
    token_one = login(client, username_one, password_one)["access_token"]

    room = create_room(client, token_one, "room-broadcast", is_private=False)
    room_id = room["id"]

    username_two, password_two = unique_user()
    register(client, username_two, password_two)
    token_two = login(client, username_two, password_two)["access_token"]
    join_room(client, token_two, room_id)

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token_one}") as ws_one:
        ws_one.receive_json()

        with client.websocket_connect(f"/ws/rooms/{room_id}?token={token_two}") as ws_two:
            ws_two.receive_json()

            ws_one.send_json({"type": MESSAGE_EVENT_TYPE, "content": "hey"})
            payload_one = ws_one.receive_json()
            payload_two = ws_two.receive_json()

            assert payload_one["type"] == MESSAGE_EVENT_TYPE
            assert payload_two["type"] == MESSAGE_EVENT_TYPE

            assert payload_one["content"] == "hey"
            assert payload_two["content"] == "hey"

            assert payload_one["id"] == payload_two["id"]