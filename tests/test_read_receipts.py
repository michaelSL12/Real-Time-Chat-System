"""
Read-receipt tests.

This file tests both REST and WebSocket read-receipt behavior.
It verifies that read markers are stored correctly, never move
backwards, are broadcast to other connected clients, and invalid
read events are rejected without breaking the connection.

Local helpers in this file are used to:
- post messages
- receive websocket messages with a timeout
"""

import threading
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import MessageRead, User
from tests.helper import (
    auth_headers,
    create_room,
    join_room,
    login,
    register,
    unique_user,
)


CONNECTED_EVENT_TYPE = "connected"
ERROR_EVENT_TYPE = "error"
PING_EVENT_TYPE = "ping"
PONG_EVENT_TYPE = "pong"
READ_EVENT_TYPE = "read"

HTTP_200_OK = 200


def recv_json_with_timeout(ws, timeout: float = 1.0) -> dict[str, Any]:
    """
    Receive a JSON message from a WebSocket with a timeout.

    This helper runs receive_json() in a background thread so the test
    does not block forever if no message arrives.

    Args:
        ws: Active WebSocket test connection.
        timeout: Maximum number of seconds to wait.

    Returns:
        The received JSON payload.

    Raises:
        TimeoutError: If no message arrives before the timeout.
        Exception: Re-raises any exception produced by receive_json().
    """
    result: dict[str, Any] = {"data": None, "err": None}

    def _target() -> None:
        try:
            result["data"] = ws.receive_json()
        except Exception as exc:
            result["err"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise TimeoutError("Timed out waiting for websocket message")

    if result["err"] is not None:
        raise result["err"]

    return result["data"]


def _post_message(
    client: TestClient,
    token: str,
    room_id: int,
    content: str,
) -> int:
    """
    Post a message to a room through the REST API and return its message ID.
    """
    response = client.post(
        f"/rooms/{room_id}/messages",
        headers=auth_headers(token),
        json={"content": content},
    )
    assert response.status_code == HTTP_200_OK, response.text
    return response.json()["id"]


def test_rest_mark_read_creates_row(client: TestClient, db_session: Session):
    """
    Verify that marking a message as read through the REST API creates
    or updates a MessageRead row in the database.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "read-room-1")
    room_id = room["id"]
    join_room(client, token, room_id)

    message_id = _post_message(client, token, room_id, "hello")

    response = client.post(
        f"/rooms/{room_id}/read/{message_id}",
        headers=auth_headers(token),
    )
    assert response.status_code == HTTP_200_OK, response.text

    body = response.json()
    assert body["room_id"] == room_id
    assert body["last_read_message_id"] == message_id

    user_id = db_session.query(User).filter(User.username == username).one().id
    read_state = db_session.query(MessageRead).filter(
        MessageRead.room_id == room_id,
        MessageRead.user_id == user_id,
    ).one()

    assert read_state.last_read_message_id == message_id


def test_rest_mark_read_does_not_move_backwards(
    client: TestClient,
    db_session: Session,
):
    """
    Verify that the read marker never moves backwards.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "read-room-2")
    room_id = room["id"]
    join_room(client, token, room_id)

    first_message_id = _post_message(client, token, room_id, "m1")
    second_message_id = _post_message(client, token, room_id, "m2")

    response = client.post(
        f"/rooms/{room_id}/read/{second_message_id}",
        headers=auth_headers(token),
    )
    assert response.status_code == HTTP_200_OK, response.text
    assert response.json()["last_read_message_id"] == second_message_id

    earlier_response = client.post(
        f"/rooms/{room_id}/read/{first_message_id}",
        headers=auth_headers(token),
    )
    assert earlier_response.status_code == HTTP_200_OK, earlier_response.text
    assert earlier_response.json()["last_read_message_id"] == second_message_id


def test_ws_read_broadcasts_to_other_clients(
    client: TestClient,
    db_session: Session,
):
    """
    Verify that a WebSocket read event is broadcast to other connected
    clients in the same room and stored in the database.
    """
    username_one, password_one = unique_user()
    register(client, username_one, password_one)
    token_one = login(client, username_one, password_one)["access_token"]

    room = create_room(client, token_one, "read-room-3")
    room_id = room["id"]
    join_room(client, token_one, room_id)

    message_id = _post_message(client, token_one, room_id, "hello")

    username_two, password_two = unique_user()
    register(client, username_two, password_two)
    token_two = login(client, username_two, password_two)["access_token"]
    join_room(client, token_two, room_id)

    user_two_id = db_session.query(User).filter(User.username == username_two).one().id

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token_one}") as ws_one:
        ws_one.receive_json()

        with client.websocket_connect(f"/ws/rooms/{room_id}?token={token_two}") as ws_two:
            ws_two.receive_json()

            ws_two.send_json({"type": READ_EVENT_TYPE, "message_id": message_id})

            payload = recv_json_with_timeout(ws_one, timeout=1.0)
            assert payload["type"] == READ_EVENT_TYPE
            assert payload["room_id"] == room_id
            assert payload["user_id"] == user_two_id
            assert payload["last_read_message_id"] == message_id

    read_state = db_session.query(MessageRead).filter(
        MessageRead.room_id == room_id,
        MessageRead.user_id == user_two_id,
    ).one()

    assert read_state.last_read_message_id == message_id


def test_ws_read_rejects_message_not_in_room(
    client: TestClient,
    db_session: Session,
):
    """
    Verify that a WebSocket read event is rejected when the message
    does not belong to the connected room.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room_a = create_room(client, token, "read-room-a")
    room_a_id = room_a["id"]
    join_room(client, token, room_a_id)

    message_id = _post_message(client, token, room_a_id, "a")

    room_b = create_room(client, token, "read-room-b")
    room_b_id = room_b["id"]
    join_room(client, token, room_b_id)

    with client.websocket_connect(f"/ws/rooms/{room_b_id}?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": READ_EVENT_TYPE, "message_id": message_id})

        payload = ws.receive_json()
        assert payload["type"] == ERROR_EVENT_TYPE
        assert (
            "room" in payload.get("detail", "").lower()
            or "not found" in payload.get("detail", "").lower()
        )


def test_ws_invalid_read_payload_stays_connected(
    client: TestClient,
    db_session: Session,
):
    """
    Verify that an invalid read payload returns an error but does not
    close the WebSocket connection.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "read-room-4")
    room_id = room["id"]
    join_room(client, token, room_id)

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token}") as ws:
        connected_payload = ws.receive_json()
        assert connected_payload["type"] == CONNECTED_EVENT_TYPE

        ws.send_json({"type": READ_EVENT_TYPE})
        error_payload = ws.receive_json()
        assert error_payload["type"] == ERROR_EVENT_TYPE

        ws.send_json({"type": PING_EVENT_TYPE})
        pong_payload = ws.receive_json()
        assert pong_payload["type"] == PONG_EVENT_TYPE